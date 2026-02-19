"""Graph metadata discovery and indexing service."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.core.database import DatabaseConnection
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier

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
            if datetime.now() - timestamp < self._ttl:
                return properties
            del self._cache[key]
        return None

    def set(self, graph_name: str, label_name: str, properties: List[str]) -> None:
        """Cache properties with current timestamp."""
        key = f"{graph_name}.{label_name}"
        self._cache[key] = (properties, datetime.now())

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
        Discover property keys for a label using PostgreSQL jsonb_object_keys.

        Finds ALL property keys (not just sampled) via a single efficient query.

        Args:
            db_conn: Database connection
            graph_name: Name of the graph
            label_name: Name of the label
            label_kind: 'v' for vertex, 'e' for edge (unused - same schema)
            sample_size: Ignored (kept for API compatibility)

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
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)

            # Use jsonb_object_keys to find all property keys in one query
            query = f"""
                SELECT DISTINCT jsonb_object_keys(properties) as prop_key
                FROM {safe_graph}.{safe_label}
                WHERE properties IS NOT NULL
                ORDER BY prop_key
            """
            rows = await db_conn.execute_query(query)
            properties = [row["prop_key"] for row in rows]
            property_cache.set(graph_name, label_name, properties)
            return properties

        except Exception as e:
            logger.warning(
                f"Failed to discover properties for {graph_name}.{label_name}: {e}"
            )
            return []

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
            logger.warning(
                f"Failed to get exact count for {graph_name}.{label_name}: {e}"
            )
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

            # Escape identifiers for safe use in SQL
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)

            # Build query to sample property values
            if label_kind == "v":
                query = f"""
                    SELECT properties->>%(prop_name)s as prop_value
                    FROM {safe_graph}.{safe_label}
                    WHERE properties ? %(prop_name)s
                    LIMIT %(limit)s
                """
            else:
                query = f"""
                    SELECT properties->>%(prop_name)s as prop_value
                    FROM {safe_graph}.{safe_label}
                    WHERE properties ? %(prop_name)s
                    LIMIT %(limit)s
                """

            rows = await db_conn.execute_query(
                query, {"prop_name": property_name, "limit": sample_size}
            )

            # Extract numeric values
            numeric_values = []
            for row in rows:
                prop_value = row.get("prop_value")
                if prop_value is not None:
                    try:
                        # Try to convert to float
                        num_value = float(prop_value)
                        numeric_values.append(num_value)
                    except (ValueError, TypeError):
                        # Not numeric, skip
                        continue

            if len(numeric_values) == 0:
                return {"min": None, "max": None}

            return {
                "min": min(numeric_values),
                "max": max(numeric_values),
            }

        except Exception as e:
            logger.warning(
                f"Failed to get property statistics for {graph_name}.{label_name}.{property_name}: {e}"
            )
            return {"min": None, "max": None}

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

