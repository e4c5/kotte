"""Node deletion endpoint for graph API."""

import logging

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import validate_graph_name
from app.models.graph import NodeDeleteResponse
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
    """Get database connection from session."""
    from app.api.v1.graph import get_db_connection as base_get_db_connection
    return base_get_db_connection(session)


@router.delete("/{graph_name}/nodes/{node_id}", response_model=NodeDeleteResponse)
async def delete_node(
    graph_name: str,
    node_id: str,
    detach: bool = Query(default=False, description="If true, delete node and all its relationships"),
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> NodeDeleteResponse:
    """
    Delete a node from the graph.
    
    Args:
        graph_name: Name of the graph
        node_id: ID of the node to delete
        detach: If true, delete node and all its relationships. If false, only delete if no relationships exist.
        db_conn: Database connection
    
    Returns:
        NodeDeleteResponse with deletion status
    """
    try:
        # Validate graph name format (prevents SQL injection)
        validated_graph_name = validate_graph_name(graph_name)
        
        # Validate node_id is numeric (AGE uses integer IDs)
        try:
            node_id_int = int(node_id)
        except ValueError:
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=f"Invalid node ID format: '{node_id}'. Node IDs must be integers.",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )
        
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": validated_graph_name}
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{validated_graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )
        
        # Check if node exists
        check_node_query = f"""
            SELECT * FROM cypher('{validated_graph_name}', $$
                MATCH (n)
                WHERE id(n) = $node_id
                RETURN n
            $$, json_build_object('node_id', %(node_id)s)::jsonb) AS (result agtype)
        """
        node_check = await db_conn.execute_query(
            check_node_query, {"node_id": node_id_int}
        )
        if not node_check:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Node with ID '{node_id}' not found in graph '{validated_graph_name}'",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )
        
        # Count edges before deletion (if detach)
        edges_deleted = 0
        if detach:
            count_edges_query = f"""
                SELECT * FROM cypher('{validated_graph_name}', $$
                    MATCH (n)-[r]-()
                    WHERE id(n) = $node_id
                    RETURN count(r) as edge_count
                $$, json_build_object('node_id', %(node_id)s)::jsonb) AS (result agtype)
            """
            edge_count_result = await db_conn.execute_query(
                count_edges_query, {"node_id": node_id_int}
            )
            if edge_count_result:
                parsed = AgTypeParser.parse(edge_count_result[0].get("result", {}))
                if isinstance(parsed, dict) and "edge_count" in parsed:
                    edges_deleted = int(parsed["edge_count"]) or 0
        
        # Delete the node
        if detach:
            delete_query = f"""
                SELECT * FROM cypher('{validated_graph_name}', $$
                    MATCH (n)
                    WHERE id(n) = $node_id
                    DETACH DELETE n
                    RETURN count(n) as deleted_count
                $$, json_build_object('node_id', %(node_id)s)::jsonb) AS (result agtype)
            """
        else:
            delete_query = f"""
                SELECT * FROM cypher('{validated_graph_name}', $$
                    MATCH (n)
                    WHERE id(n) = $node_id
                    DELETE n
                    RETURN count(n) as deleted_count
                $$, json_build_object('node_id', %(node_id)s)::jsonb) AS (result agtype)
            """
        
        delete_result = await db_conn.execute_query(
            delete_query, {"node_id": node_id_int}
        )
        
        if not delete_result:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to delete node",
                category=ErrorCategory.SYSTEM,
                status_code=500,
            )
        
        parsed_result = AgTypeParser.parse(delete_result[0].get("result", {}))
        deleted_count = 0
        if isinstance(parsed_result, dict) and "deleted_count" in parsed_result:
            deleted_count = int(parsed_result["deleted_count"]) or 0
        
        if deleted_count == 0:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Node deletion failed or node has relationships (use detach=true to delete with relationships)",
                category=ErrorCategory.SYSTEM,
                status_code=500,
            )
        
        logger.info(
            f"Deleted node {node_id} from graph {validated_graph_name} (detach={detach}, edges_deleted={edges_deleted})"
        )
        
        return NodeDeleteResponse(
            deleted=True,
            node_id=node_id,
            edges_deleted=edges_deleted,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting node {node_id} from graph {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to delete node: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e

