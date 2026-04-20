"""Graph metadata discovery and indexing service."""

import asyncio
import logging
from typing import Dict, List, Optional

from app.core.database import DatabaseConnection
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
from app.services.agtype import AgTypeParser
from app.services.cache import metadata_cache

logger = logging.getLogger(__name__)

DOES_NOT_EXIST_TEXT = "does not exist"


async def invalidate_property_metadata_cache(
    graph_name: str, label_name: Optional[str] = None
) -> None:
    """
    Drop cached metadata for a graph (and optionally one label).

    Uses ``metadata_cache`` APIs that hold the async lock (no direct ``_cache`` access).
    Clears property discovery keys for both vertex and edge kinds when a label is given.
    When only ``graph_name`` is given, clears property, count, and stats prefixes for that graph.

    Graph and label identifiers are validated before any cache key use; keys use
    ``props:{graph}:``-style prefixes with validated names to avoid cross-graph collisions.
    """
    validated_graph = validate_graph_name(graph_name)
    validated_label = validate_label_name(label_name) if label_name else None
    if validated_label:
        for kind in ("v", "e"):
            await metadata_cache.delete(f"props:{validated_graph}:{validated_label}:{kind}")
    else:
        await metadata_cache.clear(prefix=f"props:{validated_graph}:")
        await metadata_cache.clear(prefix=f"counts:{validated_graph}:")
        await metadata_cache.clear(prefix=f"stats:{validated_graph}:")


class MetadataService:
    """Service for discovering graph metadata."""

    @staticmethod
    async def discover_properties(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        label_kind: str,  # 'v' for vertex, 'e' for edge
        sample_size: int = 1000,
    ) -> List[str]:
        """
        Discover property keys for a label using Cypher keys().
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            cache_key = f"props:{validated_graph_name}:{validated_label_name}:{label_kind}"
            cached = await metadata_cache.get(cache_key)
            if cached is not None:
                return cached
            limit = min(max(1, sample_size), 500)

            if label_kind == "v":
                cypher = f"MATCH (n:{validated_label_name}) RETURN keys(n) AS k LIMIT {limit}"
            else:
                cypher = (
                    f"MATCH ()-[r:{validated_label_name}]->() RETURN keys(r) AS k LIMIT {limit}"
                )

            raw_rows = await db_conn.execute_cypher(validated_graph_name, cypher, params=None)
            all_keys: set = set()
            for row in raw_rows:
                val = next(iter(row.values()), None) if row else None
                parsed = AgTypeParser.parse(val)
                if isinstance(parsed, list):
                    for k in parsed:
                        if isinstance(k, str):
                            all_keys.add(k)
            properties = sorted(all_keys)

            await metadata_cache.set(cache_key, properties)
            return properties

        except Exception as e:
            msg = f"Failed to discover properties for {graph_name}.{label_name}: {e}"
            if DOES_NOT_EXIST_TEXT in str(e):
                logger.debug(msg)
            else:
                logger.warning(msg)
            return []

    @staticmethod
    async def get_label_count_estimates(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_kind: str,  # 'v' for vertex, 'e' for edge
    ) -> Dict[str, int]:
        """
        Get approximate counts for all labels of a given kind in one query.
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            cache_key = f"counts:{validated_graph_name}:{label_kind}"
            cached = await metadata_cache.get(cache_key)
            if cached is not None:
                return cached
            query = """
                SELECT label.name as label_name,
                       CASE
                           WHEN c.reltuples IS NULL OR c.reltuples <= 0 THEN 0
                           ELSE c.reltuples::bigint
                       END as estimate
                FROM ag_catalog.ag_label label
                JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                LEFT JOIN pg_namespace n ON n.nspname = %(graph_name)s
                LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = label.name
                WHERE graph.name = %(graph_name)s
                  AND label.kind = %(label_kind)s
            """
            rows = await db_conn.execute_query(
                query,
                {"graph_name": validated_graph_name, "label_kind": label_kind},
            )
            counts = {
                row["label_name"]: max(int(row.get("estimate") or 0), 0)
                for row in rows
                if row.get("label_name")
            }

            # Cache for a shorter duration (10 minutes)
            await metadata_cache.set(cache_key, counts, ttl_seconds=600)
            return counts
        except Exception as e:
            logger.warning(
                "Failed to get count estimates for graph %s kind %s: %s",
                graph_name,
                label_kind,
                e,
            )
            return {}

    @staticmethod
    async def get_exact_counts(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        label_kind: str,
    ) -> int:
        """
        Get exact count for a label (slower but accurate).
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)

            query = f"""
                SELECT COUNT(*) as count
                FROM {safe_graph}.{safe_label}
            """
            result = await db_conn.execute_scalar(query)
            return int(result) if result else 0
        except Exception as e:
            msg = f"Failed to get exact count for {graph_name}.{label_name}: {e}"
            if DOES_NOT_EXIST_TEXT in str(e):
                logger.debug(msg)
            else:
                logger.warning(msg)
            return 0

    @staticmethod
    def _build_stats_query(label_name: str, label_kind: str, limit: int) -> str:
        """Helper to build statistics Cypher query."""
        if label_kind == "v":
            return f"MATCH (n:{label_name}) RETURN n[$key] AS val LIMIT {limit}"
        return f"MATCH ()-[r:{label_name}]->() RETURN r[$key] AS val LIMIT {limit}"

    @staticmethod
    async def get_property_statistics(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        label_kind: str,
        property_name: str,
        sample_size: int = 1000,
    ) -> Dict[str, Optional[float]]:
        """
        Get statistics (min, max) for a numeric property.
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            cache_key = (
                f"stats:{validated_graph_name}:{validated_label_name}:"
                f"{label_kind}:{property_name}"
            )
            cached = await metadata_cache.get(cache_key)
            if cached is not None:
                return cached
            limit = min(max(1, sample_size), 5000)

            cypher = MetadataService._build_stats_query(validated_label_name, label_kind, limit)
            raw_rows = await db_conn.execute_cypher(
                validated_graph_name,
                cypher,
                params={"key": property_name},
            )

            numeric_values = []
            for row in raw_rows:
                val = next(iter(row.values()), None) if row else None
                parsed = AgTypeParser.parse(val)
                if parsed is not None:
                    try:
                        numeric_values.append(float(parsed))
                    except (ValueError, TypeError):
                        continue

            stats = {"min": None, "max": None}
            if numeric_values:
                stats = {"min": min(numeric_values), "max": max(numeric_values)}

            await metadata_cache.set(cache_key, stats)
            return stats

        except Exception as e:
            msg = f"Failed to get property statistics for {graph_name}.{label_name}.{property_name}: {e}"
            if DOES_NOT_EXIST_TEXT in str(e):
                logger.debug(msg)
            else:
                logger.warning(msg)
            return {"min": None, "max": None}

    @staticmethod
    async def get_numeric_property_statistics_for_label(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        *,
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Min/max statistics for each numeric edge property on a label.

        If ``properties`` is omitted, discovers edge property keys first (extra round trip).
        """
        props = properties
        if props is None:
            props = await MetadataService.discover_properties(db_conn, graph_name, label_name, "e")
        if not props:
            return {}

        async def stats_for(prop: str) -> tuple[str, Dict[str, Optional[float]]]:
            s = await MetadataService.get_property_statistics(
                db_conn, graph_name, label_name, "e", prop
            )
            return prop, s

        pairs = await asyncio.gather(*[stats_for(p) for p in props])
        out: Dict[str, Dict[str, Optional[float]]] = {}
        for prop, stats in pairs:
            if stats.get("min") is not None and stats.get("max") is not None:
                out[prop] = stats
        return out

    @staticmethod
    async def create_label_indices(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        label_kind: str,
    ) -> None:
        """
        Create foundational indices for a given label.
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)

            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)
            table_name = f"{safe_graph}.{safe_label}"

            columns: list[str] = ["id"]
            if label_kind == "e":
                columns.extend(["start_id", "end_id"])

            for column in columns:
                index_name = f"idx_{validated_graph_name}_{validated_label_name}_{column}"
                create_index_sql = f"""
                    CREATE INDEX IF NOT EXISTS {escape_identifier(index_name)}
                    ON {table_name} ({column})
                """
                await db_conn.execute_command(create_index_sql)

            logger.info(f"Ensured indices on {table_name} for columns: {', '.join(columns)}")
            await invalidate_property_metadata_cache(validated_graph_name)
        except Exception as e:
            logger.warning(
                f"Failed to create indices for {graph_name}.{label_name} ({label_kind}): {e}"
            )

    @staticmethod
    async def analyze_table(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
    ) -> None:
        """Run ANALYZE on a table to update statistics for accurate count estimates."""
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)
            await db_conn.execute_command(f"ANALYZE {safe_graph}.{safe_label}")
            logger.info("Updated statistics for %s.%s", validated_graph_name, validated_label_name)
            await invalidate_property_metadata_cache(validated_graph_name)
        except Exception as e:
            logger.warning("Failed to analyze table %s.%s: %s", graph_name, label_name, e)
