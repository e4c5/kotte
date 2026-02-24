"""Graph metadata discovery and indexing service."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.core.database import DatabaseConnection
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)


class PropertyCache:
    """Cache discovered properties with TTL to avoid repeated queries."""

    def __init__(self, ttl_minutes: int = 60):
        self._cache: Dict[str, Tuple[List[str], datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, graph_name: str, label_name: str) -> Optional[List[str]]:
        """Get cached properties if not expired."""
        key = f"{graph_name}.{label_name}"
        if key in self._cache:
            properties, timestamp = self._cache[key]
            if datetime.now(timezone.utc) - timestamp < self._ttl:
                return properties
            del self._cache[key]
        return None

    def set(self, graph_name: str, label_name: str, properties: List[str]) -> None:
        """Cache properties with current timestamp."""
        key = f"{graph_name}.{label_name}"
        self._cache[key] = (properties, datetime.now(timezone.utc))

    def invalidate(self, graph_name: str, label_name: Optional[str] = None) -> None:
        """Invalidate cache for graph or specific label."""
        if label_name:
            key = f"{graph_name}.{label_name}"
            self._cache.pop(key, None)
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{graph_name}.")]
            for key in keys_to_remove:
                del self._cache[key]


property_cache = PropertyCache(ttl_minutes=60)


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

        AGE stores properties as agtype, not jsonb, so we use Cypher to sample
        nodes/edges and merge property keys instead of raw SQL jsonb functions.

        Args:
            db_conn: Database connection
            graph_name: Name of the graph
            label_name: Name of the label
            label_kind: 'v' for vertex, 'e' for edge
            sample_size: Max number of rows to sample for key discovery (default 1000)

        Returns:
            List of property keys found
        """
        # Check cache first
        cached = property_cache.get(graph_name, label_name)
        if cached is not None:
            return cached

        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            limit = min(max(1, sample_size), 500)

            if label_kind == "v":
                cypher = (
                    f"MATCH (n:{validated_label_name}) RETURN keys(n) AS k LIMIT {limit}"
                )
            else:
                cypher = (
                    f"MATCH ()-[r:{validated_label_name}]->() RETURN keys(r) AS k LIMIT {limit}"
                )

            raw_rows = await db_conn.execute_cypher(
                validated_graph_name, cypher, params=None
            )
            all_keys: set = set()
            for row in raw_rows:
                # execute_cypher returns one column (e.g. "k" from RETURN keys(n) AS k)
                val = next(iter(row.values()), None) if row else None
                parsed = AgTypeParser.parse(val)
                if isinstance(parsed, list):
                    for k in parsed:
                        if isinstance(k, str):
                            all_keys.add(k)
            properties = sorted(all_keys)
            property_cache.set(graph_name, label_name, properties)
            return properties

        except Exception as e:
            msg = f"Failed to discover properties for {graph_name}.{label_name}: {e}"
            if "does not exist" in str(e):
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

        Args:
            db_conn: Database connection.
            graph_name: Name of the graph (validated via validate_graph_name).
            label_kind: Label kind ('v' for vertex, 'e' for edge).

        Returns:
            Mapping of label name to non-negative approximate row count.
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
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
            return {
                row["label_name"]: max(int(row.get("estimate") or 0), 0)
                for row in rows
                if row.get("label_name")
            }
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

        Args:
            db_conn: Database connection
            graph_name: Name of the graph
            label_name: Name of the label
            label_kind: 'v' for vertex, 'e' for edge

        Returns:
            Exact count of records
        """
        try:
            # Validate names (defense in depth)
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)

            # Escape identifiers for safe use in SQL
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)

            # Use escaped names for defense in depth
            query = f"""
                SELECT COUNT(*) as count
                FROM {safe_graph}.{safe_label}
            """
            result = await db_conn.execute_scalar(query)
            return int(result) if result else 0
        except Exception as e:
            msg = f"Failed to get exact count for {graph_name}.{label_name}: {e}"
            if "does not exist" in str(e):
                logger.debug(msg)
            else:
                logger.warning(msg)
            return 0

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

        Args:
            db_conn: Database connection
            graph_name: Name of the graph
            label_name: Name of the label
            label_kind: 'v' for vertex, 'e' for edge
            property_name: Name of the property to analyze
            sample_size: Number of records to sample

        Returns:
            Dictionary with 'min' and 'max' values, or None if property is not numeric
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)
            limit = min(max(1, sample_size), 5000)

            # AGE uses agtype for properties; sample via Cypher with parameterized key
            if label_kind == "v":
                cypher = (
                    f"MATCH (n:{validated_label_name}) RETURN n[$key] AS val LIMIT $limit"
                )
            else:
                cypher = (
                    f"MATCH ()-[r:{validated_label_name}]->() RETURN r[$key] AS val LIMIT $limit"
                )
            raw_rows = await db_conn.execute_cypher(
                validated_graph_name,
                cypher,
                params={"key": property_name, "limit": limit},
            )
            numeric_values = []
            for row in raw_rows:
                # execute_cypher returns one column (e.g. "val" from RETURN n[$key] AS val)
                val = next(iter(row.values()), None) if row else None
                parsed = AgTypeParser.parse(val)
                if parsed is not None:
                    try:
                        numeric_values.append(float(parsed))
                    except (ValueError, TypeError):
                        continue
            if not numeric_values:
                return {"min": None, "max": None}
            return {"min": min(numeric_values), "max": max(numeric_values)}

        except Exception as e:
            msg = f"Failed to get property statistics for {graph_name}.{label_name}.{property_name}: {e}"
            if "does not exist" in str(e):
                logger.debug(msg)
            else:
                logger.warning(msg)
            return {"min": None, "max": None}

    @staticmethod
    async def get_numeric_property_statistics_for_label(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
    ) -> Dict[str, Dict[str, Optional[float]]]:
        """
        Get min/max statistics for all numeric properties of a label.

        AGE stores properties as agtype, not jsonb, so we do not use raw SQL
        with CROSS JOIN LATERAL jsonb_each_text. Callers can still get per-property
        stats via get_property_statistics for each key from discover_properties.
        """
        # Return empty; per-property stats are available via get_property_statistics
        return {}

    @staticmethod
    async def create_label_indices(
        db_conn: DatabaseConnection,
        graph_name: str,
        label_name: str,
        label_kind: str,
    ) -> None:
        """
        Create foundational indices for a given label.

        For vertices, creates an index on id.
        For edges, creates indices on id, start_id, and end_id.
        """
        try:
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)

            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)
            table_name = f"{safe_graph}.{safe_label}"

            # Always index id; for edges also index start_id and end_id
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

            logger.info(
                f"Ensured indices on {table_name} for columns: {', '.join(columns)}"
            )
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
        except Exception as e:
            logger.warning("Failed to analyze table %s.%s: %s", graph_name, label_name, e)
