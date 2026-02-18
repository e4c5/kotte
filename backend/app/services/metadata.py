"""Graph metadata discovery service."""

import logging
from typing import Dict, List, Optional, Set

from app.core.database import DatabaseConnection
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier

logger = logging.getLogger(__name__)


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
        Discover property keys for a label by sampling data.

        Args:
            db_conn: Database connection
            graph_name: Name of the graph
            label_name: Name of the label
            label_kind: 'v' for vertex, 'e' for edge
            sample_size: Number of records to sample

        Returns:
            List of property keys found
        """
        try:
            # Validate names (defense in depth - should already be validated)
            validated_graph_name = validate_graph_name(graph_name)
            validated_label_name = validate_label_name(label_name)

            # Escape identifiers for safe use in SQL
            safe_graph = escape_identifier(validated_graph_name)
            safe_label = escape_identifier(validated_label_name)
            
            # Build query to sample properties
            # Use validated names (already validated for SQL injection)
            if label_kind == "v":
                # For vertices, query the vertex table
                query = f"""
                    SELECT properties
                    FROM {safe_graph}.{safe_label}
                    LIMIT %(limit)s
                """
            else:
                # For edges, query the edge table
                query = f"""
                    SELECT properties
                    FROM {safe_graph}.{safe_label}
                    LIMIT %(limit)s
                """

            rows = await db_conn.execute_query(
                query, {"limit": sample_size}
            )

            # Collect all unique property keys
            property_keys: Set[str] = set()
            for row in rows:
                properties = row.get("properties", {})
                if isinstance(properties, dict):
                    property_keys.update(properties.keys())

            return sorted(list(property_keys))

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

