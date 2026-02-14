"""Graph metadata endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.models.graph import (
    GraphInfo,
    GraphMetadata,
    MetaGraphResponse,
    NodeLabel,
    EdgeLabel,
    MetaGraphEdge,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
    """Get database connection from session."""
    db_conn = session.get("db_connection")
    if not db_conn:
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message="Database connection not established",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        )
    return db_conn


@router.get("", response_model=list[GraphInfo])
async def list_graphs(
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> list[GraphInfo]:
    """List all available AGE graphs in the database."""
    try:
        # Query AGE catalog for graphs
        query = """
            SELECT name, graphid
            FROM ag_catalog.ag_graph
            ORDER BY name
        """
        rows = await db_conn.execute_query(query)

        return [
            GraphInfo(name=row["name"], id=str(row["graphid"]))
            for row in rows
        ]
    except Exception as e:
        logger.exception("Error listing graphs")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to list graphs: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e


@router.get("/{graph_name}/metadata", response_model=GraphMetadata)
async def get_graph_metadata(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> GraphMetadata:
    """Get metadata for a specific graph."""
    try:
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": graph_name}
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )

        # Get node labels with counts
        node_query = """
            SELECT DISTINCT label.name as label_name
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'v'
            ORDER BY label_name
        """
        node_label_rows = await db_conn.execute_query(
            node_query, {"graph_name": graph_name}
        )

        node_labels = []
        for row in node_label_rows:
            label_name = row["label_name"]
            # Get count (using ANALYZE estimates for performance)
            count_query = f"""
                SELECT reltuples::bigint as estimate
                FROM pg_class
                WHERE relname = '{graph_name}_{label_name}'
            """
            count = await db_conn.execute_scalar(count_query) or 0

            # Get properties (simplified - would need to query actual data)
            properties = []  # TODO: Implement property discovery

            node_labels.append(
                NodeLabel(label=label_name, count=int(count), properties=properties)
            )

        # Get edge labels with counts
        edge_query = """
            SELECT DISTINCT label.name as label_name
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            ORDER BY label_name
        """
        edge_label_rows = await db_conn.execute_query(
            edge_query, {"graph_name": graph_name}
        )

        edge_labels = []
        for row in edge_label_rows:
            label_name = row["label_name"]
            # Get count estimate
            count_query = f"""
                SELECT reltuples::bigint as estimate
                FROM pg_class
                WHERE relname = '{graph_name}_{label_name}'
            """
            count = await db_conn.execute_scalar(count_query) or 0

            properties = []  # TODO: Implement property discovery

            edge_labels.append(
                EdgeLabel(label=label_name, count=int(count), properties=properties)
            )

        return GraphMetadata(
            graph_name=graph_name,
            node_labels=node_labels,
            edge_labels=edge_labels,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error getting metadata for graph {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get graph metadata: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e


@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    # TODO: Implement meta-graph discovery
    # This would query actual graph data to find patterns like:
    # (Person)-[:KNOWS]->(Person), (Person)-[:WORKS_AT]->(Company), etc.

    # Placeholder implementation
    return MetaGraphResponse(
        graph_name=graph_name,
        relationships=[],
    )

