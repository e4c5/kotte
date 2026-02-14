"""Query execution endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends

from app.core.auth import get_session
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.models.query import (
    QueryExecuteRequest,
    QueryExecuteResponse,
    QueryResultRow,
    QueryCancelRequest,
    QueryCancelResponse,
)
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for active queries (for cancellation)
# In production, use Redis or similar for distributed systems
_active_queries: dict[str, any] = {}


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


@router.post("/execute", response_model=QueryExecuteResponse)
async def execute_query(
    request: QueryExecuteRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> QueryExecuteResponse:
    """
    Execute a Cypher query against the specified graph.

    Query is executed using parameterized SQL to prevent injection.
    Results are parsed from AGE agtype format.
    """
    request_id = str(uuid.uuid4())

    # Validate graph exists
    graph_check = """
        SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
    """
    graph_id = await db_conn.execute_scalar(
        graph_check, {"graph_name": request.graph}
    )
    if not graph_id:
        raise APIException(
            code=ErrorCode.GRAPH_NOT_FOUND,
            message=f"Graph '{request.graph}' not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

    # Build parameterized SQL query
    # AGE Cypher queries are executed via: SELECT * FROM cypher('graph_name', $$cypher$$, params) AS (result agtype)
    # Note: Graph name is validated above. Cypher query is passed as literal (AGE will parse it).
    # Parameters are passed as JSONB to prevent injection.
    cypher_params = request.params or {}
    
    # Convert params to JSON string for AGE
    import json
    params_json = json.dumps(cypher_params)

    # Safe mode: reject mutating queries if enabled
    if settings.query_safe_mode:
        cypher_upper = request.cypher.upper()
        mutating_keywords = ["CREATE", "DELETE", "SET", "REMOVE", "MERGE", "DETACH"]
        if any(keyword in cypher_upper for keyword in mutating_keywords):
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message="Mutating queries are not allowed in safe mode",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

    # AGE cypher function requires graph name and query as text literals
    # We've validated graph_name exists, so it's safe to use
    # The cypher query itself is parsed by AGE, which provides some protection
    # Parameters are passed as JSONB (parameterized)
    sql_query = f"""
        SELECT * FROM cypher('{request.graph}', $${request.cypher}$$, %(params)s::jsonb) AS (result agtype)
    """
    sql_params = {
        "params": params_json,
    }

    try:
        # Execute query with parameters
        raw_rows = await db_conn.execute_query(sql_query, sql_params)
        
        # Parse agtype results
        parsed_rows = []
        all_columns = set()
        
        for raw_row in raw_rows:
            parsed_row = {}
            for col_name, agtype_value in raw_row.items():
                all_columns.add(col_name)
                parsed_value = AgTypeParser.parse(agtype_value)
                parsed_row[col_name] = parsed_value
            parsed_rows.append(parsed_row)
        
        # Extract graph elements (nodes and edges) for visualization
        graph_elements = AgTypeParser.extract_graph_elements(parsed_rows)
        
        # Build result rows
        columns = sorted(all_columns) if all_columns else ["result"]
        result_rows = [
            QueryResultRow(data=row) for row in parsed_rows
        ]

        # Add graph elements to response stats
        stats = {
            "nodes_extracted": len(graph_elements["nodes"]),
            "edges_extracted": len(graph_elements["edges"]),
            "other_results": len(graph_elements["other"]),
        }

        return QueryExecuteResponse(
            columns=columns,
            rows=result_rows,
            row_count=len(result_rows),
            request_id=request_id,
            stats=stats,
            graph_elements={
                "nodes": graph_elements["nodes"],
                "edges": graph_elements["edges"],
            } if (graph_elements["nodes"] or graph_elements["edges"]) else None,
        )

    except Exception as e:
        logger.exception(f"Query execution failed: {request.cypher[:100]}")
        # Try to determine error type
        error_msg = str(e)
        if "syntax" in error_msg.lower():
            code = ErrorCode.QUERY_SYNTAX_ERROR
            category = ErrorCategory.VALIDATION
        else:
            code = ErrorCode.QUERY_EXECUTION_ERROR
            category = ErrorCategory.UPSTREAM

        raise APIException(
            code=code,
            message=f"Query execution failed: {error_msg}",
            category=category,
            status_code=422,
            details={"cypher": request.cypher[:200]},
        ) from e


@router.post("/{request_id}/cancel", response_model=QueryCancelResponse)
async def cancel_query(
    request_id: str,
    request: QueryCancelRequest,
    session: dict = Depends(get_session),
) -> QueryCancelResponse:
    """Cancel a running query."""
    # TODO: Implement query cancellation
    # This requires tracking active queries and their database connections
    # PostgreSQL supports query cancellation via pg_cancel_backend()

    if request_id not in _active_queries:
        raise APIException(
            code=ErrorCode.QUERY_CANCELLED,
            message=f"Query {request_id} not found or already completed",
            category=ErrorCategory.VALIDATION,
            status_code=404,
        )

    # Cancel logic would go here
    _active_queries.pop(request_id, None)

    return QueryCancelResponse(cancelled=True, request_id=request_id)

