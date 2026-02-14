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
from app.services.metadata import MetadataService

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
            # For small graphs, we could use exact counts
            count_query = f"""
                SELECT reltuples::bigint as estimate
                FROM pg_class
                WHERE relname = '{graph_name}_{label_name}'
            """
            count = await db_conn.execute_scalar(count_query) or 0

            # Discover properties by sampling
            properties = await MetadataService.discover_properties(
                db_conn, graph_name, label_name, "v"
            )

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

            # Discover properties by sampling
            properties = await MetadataService.discover_properties(
                db_conn, graph_name, label_name, "e"
            )

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

        # Query to discover label-to-label patterns via edges
        # This queries the edge tables to find which node labels connect via which edge labels
        meta_query = f"""
            WITH edge_labels AS (
                SELECT DISTINCT label.name as edge_label
                FROM ag_catalog.ag_label label
                JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            )
            SELECT 
                e.edge_label,
                COUNT(*) as count
            FROM edge_labels e
            CROSS JOIN LATERAL (
                SELECT start_id, end_id
                FROM {graph_name}.{e.edge_label}
                LIMIT 1000
            ) edge_sample
            GROUP BY e.edge_label
        """

        # Simplified approach: query each edge label to find source/target patterns
        # Get all edge labels
        edge_query = """
            SELECT DISTINCT label.name as edge_label
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            ORDER BY edge_label
        """
        edge_rows = await db_conn.execute_query(edge_query, {"graph_name": graph_name})

        relationships = []
        for edge_row in edge_rows:
            edge_label = edge_row["edge_label"]
            try:
                # Sample edges to discover source/target label patterns
                sample_query = f"""
                    SELECT 
                        start_id,
                        end_id
                    FROM {graph_name}.{edge_label}
                    LIMIT 100
                """
                samples = await db_conn.execute_query(sample_query)

                # For each sample, find the labels of start and end nodes
                # This is a simplified approach - in production, you'd want to
                # query the vertex tables more efficiently
                for sample in samples[:10]:  # Limit to avoid too many queries
                    start_id = sample.get("start_id")
                    end_id = sample.get("end_id")

                    # Find source label
                    source_query = f"""
                        SELECT label.name as label_name
                        FROM ag_catalog.ag_label label
                        JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                        WHERE graph.name = %(graph_name)s AND label.kind = 'v'
                        LIMIT 1
                    """
                    # Simplified: we'd need to check which vertex table contains the ID
                    # For now, use a pattern-based approach

                # For simplicity, create a relationship entry
                # In a full implementation, we'd aggregate these properly
                relationships.append(
                    MetaGraphEdge(
                        source_label="*",  # Would be discovered from actual data
                        target_label="*",
                        edge_label=edge_label,
                        count=len(samples),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to analyze edge label {edge_label}: {e}")
                continue

        return MetaGraphResponse(
            graph_name=graph_name,
            relationships=relationships,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error getting meta-graph for {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get meta-graph: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e

