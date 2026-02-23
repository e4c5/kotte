"""Node deletion endpoint for graph API."""

import logging

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory, translate_db_error
from app.core.validation import validate_graph_name
from app.core.metrics import metrics
from app.models.graph import NodeDeleteResponse
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
    """Get database connection from session."""
    from app.api.v1.graph import get_db_connection as base_get_db_connection
    return await base_get_db_connection(session)


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
        
        node_id_param = {"node_id": node_id_int}

        # Wrap check + deletion in a single transaction for atomicity
        async with db_conn.transaction():
            # Check if node exists
            node_check = await db_conn.execute_cypher(
                validated_graph_name,
                "MATCH (n) WHERE id(n) = $node_id RETURN n",
                params=node_id_param,
            )
            if not node_check:
                raise APIException(
                    code=ErrorCode.GRAPH_NOT_FOUND,
                    message=f"Node with ID '{node_id}' not found in graph '{validated_graph_name}'",
                    category=ErrorCategory.NOT_FOUND,
                    status_code=404,
                )

            # Count edges: required when !detach (to return 4xx), and when detach (for edges_deleted)
            edge_count_result = await db_conn.execute_cypher(
                validated_graph_name,
                "MATCH (n)-[r]-() WHERE id(n) = $node_id RETURN count(r) as edge_count",
                params=node_id_param,
            )
            edges_deleted = 0
            if edge_count_result:
                first_val = next(
                    iter(edge_count_result[0].values()), None
                ) if edge_count_result[0] else None
                parsed = AgTypeParser.parse(first_val)
                if isinstance(parsed, dict) and "edge_count" in parsed:
                    edges_deleted = int(parsed["edge_count"]) or 0
                elif isinstance(parsed, (int, float)):
                    edges_deleted = int(parsed)
                elif isinstance(parsed, str) and parsed.strip().isdigit():
                    edges_deleted = int(parsed)
            if not detach and edges_deleted > 0:
                raise APIException(
                    code=ErrorCode.QUERY_VALIDATION_ERROR,
                    message="Node has relationships; use detach=true to delete with relationships",
                    category=ErrorCategory.VALIDATION,
                    status_code=422,
                )

            # Delete the node
            if detach:
                delete_cypher = "MATCH (n) WHERE id(n) = $node_id DETACH DELETE n RETURN count(n) as deleted_count"
            else:
                delete_cypher = "MATCH (n) WHERE id(n) = $node_id DELETE n RETURN count(n) as deleted_count"
            delete_result = await db_conn.execute_cypher(
                validated_graph_name, delete_cypher, params=node_id_param
            )

            if not delete_result:
                raise APIException(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Failed to delete node",
                    category=ErrorCategory.SYSTEM,
                    status_code=500,
                )

            first_val = next(iter(delete_result[0].values()), None) if delete_result[0] else None
            parsed_result = AgTypeParser.parse(first_val)
            if isinstance(parsed_result, dict) and "deleted_count" in parsed_result:
                deleted_count = int(parsed_result["deleted_count"]) or 0
            elif isinstance(parsed_result, (int, float)):
                deleted_count = int(parsed_result)
            elif isinstance(parsed_result, str) and parsed_result.strip().isdigit():
                deleted_count = int(parsed_result)
            else:
                deleted_count = 0

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

            # Record metrics
            metrics.record_node_operation("delete", validated_graph_name)

            return NodeDeleteResponse(
                deleted=True,
                node_id=node_id,
                edges_deleted=edges_deleted,
            )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting node {node_id} from graph {graph_name}")
        api_exc = translate_db_error(
            e,
            context={"graph": validated_graph_name, "node_id": node_id},
        )
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to delete node: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={"graph": validated_graph_name, "node_id": node_id},
        ) from e
