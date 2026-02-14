"""Graph metadata discovery service."""

import logging
from typing import Dict, List, Set

from app.core.database import DatabaseConnection

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
            # Build query to sample properties
            if label_kind == "v":
                # For vertices, query the vertex table
                query = f"""
                    SELECT properties
                    FROM {graph_name}.{label_name}
                    LIMIT %(limit)s
                """
            else:
                # For edges, query the edge table
                query = f"""
                    SELECT properties
                    FROM {graph_name}.{label_name}
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
            query = f"""
                SELECT COUNT(*) as count
                FROM {graph_name}.{label_name}
            """
            result = await db_conn.execute_scalar(query)
            return int(result) if result else 0
        except Exception as e:
            logger.warning(
                f"Failed to get exact count for {graph_name}.{label_name}: {e}"
            )
            return 0

