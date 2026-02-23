"""Query execution endpoints."""

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends

from app.core.auth import get_session
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import (
    APIException,
    ErrorCode,
    ErrorCategory,
    GraphCypherSyntaxError,
    translate_db_error,
)
from app.core.validation import (
    add_result_limit_if_missing,
    validate_graph_name,
    validate_query_length,
    validate_variable_length_traversal,
)
from app.models.query import (
    QueryExecuteRequest,
    QueryExecuteResponse,
    QueryResultRow,
    QueryCancelRequest,
    QueryCancelResponse,
)
from app.services.agtype import AgTypeParser
from app.services.query_tracker import query_tracker
from app.services.query_templates import get_templates
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/templates")
async def list_query_templates():
    """List available Cypher query templates for common graph patterns."""
    return get_templates()


async def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
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
    session: dict = Depends(get_session),
) -> QueryExecuteResponse:
    """
    Execute a Cypher query against the specified graph.

    Query is executed using parameterized SQL to prevent injection.
    Results are parsed from AGE agtype format.
    """
    request_id = str(uuid.uuid4())
    user_id = session.get("user_id", "unknown")

    # Validate graph name format (prevents SQL injection)
    validated_graph_name = validate_graph_name(request.graph)
    
    # Validate query length
    validate_query_length(request.cypher)
    validate_variable_length_traversal(
        request.cypher, settings.query_max_variable_hops
    )

    # Apply result caps (visualization cap is stricter than generic query cap)
    if request.for_visualization:
        cypher_to_execute, limit_added = add_result_limit_if_missing(
            request.cypher, settings.max_nodes_for_graph
        )
        applied_limit = settings.max_nodes_for_graph if limit_added else None
    else:
        cypher_to_execute, limit_added = add_result_limit_if_missing(
            request.cypher, settings.query_max_result_rows
        )
        applied_limit = settings.query_max_result_rows if limit_added else None
    
    # Register query for cancellation tracking
    query_tracker.register_query(
        request_id=request_id,
        db_conn=db_conn,
        query_text=request.cypher[:200],  # Store truncated query for logging
        user_id=user_id,
    )
    
    # Get backend PID for cancellation (before query execution)
    # This PID will be used to cancel the query if needed
    try:
        backend_pid = await db_conn.get_backend_pid()
        if backend_pid:
            await query_tracker.set_backend_pid(request_id, backend_pid)
            logger.debug(f"Tracking query {request_id[:8]}... with backend PID {backend_pid}")
    except Exception as e:
        logger.warning(f"Failed to get backend PID for query tracking: {e}")

    # Validate graph exists (using parameterized query)
    graph_check = """
        SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
    """
    try:
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": validated_graph_name}
        )
    except Exception as e:
        logger.exception("Graph existence check failed")
        api_exc = translate_db_error(e, context={"graph": request.graph})
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.QUERY_EXECUTION_ERROR,
            message=f"Database error while checking graph: {e!s}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        ) from e
    if not graph_id:
        raise APIException(
            code=ErrorCode.GRAPH_NOT_FOUND,
            message=f"Graph '{validated_graph_name}' not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
        )

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

    # Log what the user submitted verbatim (for debugging query execution)
    logger.info(
        "Query execute: graph=%s, cypher_len=%s, params=%s",
        validated_graph_name,
        len(request.cypher),
        request.params,
    )
    logger.info("Query execute: user cypher verbatim: %s", request.cypher)

    # Execute via literal SQL (graph + query as literals) so AGE cypher() is called without
    # parameter overload issues; params when present are passed as a single bind.
    query_start_time = time.time()
    try:
        raw_rows = await db_conn.execute_cypher(
            validated_graph_name,
            cypher_to_execute,
            params=request.params or None,
            timeout=settings.query_timeout,
        )
        
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
        nodes_count = len(graph_elements["nodes"])
        edges_count = len(graph_elements["edges"])

        # Debug (log at DEBUG level): raw row structure when we get nodes but no edges
        if edges_count == 0 and nodes_count > 0 and raw_rows:
            logger.debug(
                "agtype_debug: 0 edges but %s nodes — first raw row structure",
                nodes_count,
            )
            first_raw = raw_rows[0]
            for col_name, raw_val in first_raw.items():
                if isinstance(raw_val, dict):
                    logger.debug("agtype_debug: column %r = dict keys=%s", col_name, list(raw_val.keys()))
                elif isinstance(raw_val, str):
                    logger.debug(
                        "agtype_debug: column %r = str len=%s prefix=%s",
                        col_name,
                        len(raw_val),
                        raw_val[:350] if raw_val else "",
                    )
                else:
                    logger.debug(
                        "agtype_debug: column %r type=%s repr=%s",
                        col_name,
                        type(raw_val).__name__,
                        repr(raw_val)[:350],
                    )

        # Build result rows
        columns = sorted(all_columns) if all_columns else ["result"]
        result_rows = [
            QueryResultRow(data=row) for row in parsed_rows
        ]

        # Add graph elements to response stats
        paths_list = graph_elements.get("paths", [])
        stats = {
            "nodes_extracted": nodes_count,
            "edges_extracted": edges_count,
            "paths_extracted": len(paths_list),
            "other_results": len(graph_elements["other"]),
        }
        if limit_added and applied_limit is not None:
            stats["guardrail_limit_applied"] = True
            stats["guardrail_limit"] = applied_limit

        # Check visualization limits
        visualization_warning = None
        if nodes_count > settings.max_nodes_for_graph or edges_count > settings.max_edges_for_graph:
            if nodes_count > settings.max_nodes_for_graph and edges_count > settings.max_edges_for_graph:
                visualization_warning = (
                    f"Result too large for graph visualization ({nodes_count} nodes, {edges_count} edges). "
                    f"Maximum: {settings.max_nodes_for_graph} nodes, {settings.max_edges_for_graph} edges. "
                    "Use table view or refine your query with LIMIT or WHERE filters."
                )
            elif nodes_count > settings.max_nodes_for_graph:
                visualization_warning = (
                    f"Result too large for graph visualization ({nodes_count} nodes). "
                    f"Maximum: {settings.max_nodes_for_graph} nodes. "
                    "Use table view or refine your query with LIMIT or WHERE filters."
                )
            else:
                visualization_warning = (
                    f"Result too large for graph visualization ({edges_count} edges). "
                    f"Maximum: {settings.max_edges_for_graph} edges. "
                    "Use table view or refine your query with LIMIT or WHERE filters."
                )

        # Unregister query on successful completion
        query_tracker.unregister_query(request_id)

        # Record metrics
        query_duration = time.time() - query_start_time
        metrics.record_query_execution(
            graph=validated_graph_name,
            status="success",
            duration=query_duration,
            row_count=len(result_rows),
        )

        return QueryExecuteResponse(
            columns=columns,
            rows=result_rows,
            row_count=len(result_rows),
            request_id=request_id,
            stats=stats,
            graph_elements={
                "nodes": graph_elements["nodes"],
                "edges": graph_elements["edges"],
                "paths": paths_list,
            } if (graph_elements["nodes"] or graph_elements["edges"] or paths_list) else None,
            visualization_warning=visualization_warning,
        )

    except asyncio.TimeoutError:
        # Query timeout
        query_tracker.unregister_query(request_id)
        query_duration = time.time() - query_start_time
        metrics.record_query_execution(
            graph=validated_graph_name,
            status="timeout",
            duration=query_duration,
        )
        metrics.record_error(ErrorCode.QUERY_TIMEOUT, ErrorCategory.UPSTREAM)
        raise APIException(
            code=ErrorCode.QUERY_TIMEOUT,
            message=f"Query execution timed out after {settings.query_timeout} seconds",
            category=ErrorCategory.UPSTREAM,
            status_code=504,
            retryable=True,
        )
    except Exception as e:
        query_tracker.unregister_query(request_id)
        query_duration = time.time() - query_start_time
        logger.exception(f"Query execution failed: {request.cypher[:100]}")
        error_msg = str(e)

        # Constraint violations (UniqueViolation, ForeignKeyViolation, etc.)
        api_exc = translate_db_error(
            e,
            context={
                "graph": validated_graph_name,
                "query": cypher_to_execute[:500],
                "params": (
                    {k: str(v)[:100] for k, v in (request.params or {}).items()}
                    if request.params
                    else None
                ),
            },
        )
        if api_exc:
            metrics.record_query_execution(
                graph=validated_graph_name, status="error", duration=query_duration
            )
            metrics.record_error(
                ErrorCode.GRAPH_CONSTRAINT_VIOLATION, ErrorCategory.VALIDATION
            )
            raise api_exc from e

        if "syntax" in error_msg.lower():
            metrics.record_query_execution(
                graph=validated_graph_name, status="error", duration=query_duration
            )
            metrics.record_error(ErrorCode.CYPHER_SYNTAX_ERROR, ErrorCategory.VALIDATION)
            raise GraphCypherSyntaxError(cypher_to_execute, error_msg) from e

        metrics.record_query_execution(
            graph=validated_graph_name, status="error", duration=query_duration
        )
        metrics.record_error(ErrorCode.QUERY_EXECUTION_ERROR, ErrorCategory.UPSTREAM)
        raise APIException(
            code=ErrorCode.QUERY_EXECUTION_ERROR,
            message=f"Query execution failed: {error_msg}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            details={
                "graph": validated_graph_name,
                "query": request.cypher[:500],
                "error": error_msg,
                "params": (
                    {k: str(v)[:100] for k, v in (request.params or {}).items()}
                    if request.params
                    else None
                ),
            },
        ) from e


@router.post("/{request_id}/cancel", response_model=QueryCancelResponse)
async def cancel_query(
    request_id: str,
    request: QueryCancelRequest,
    session: dict = Depends(get_session),
) -> QueryCancelResponse:
    """
    Cancel a running query.
    
    Uses PostgreSQL pg_cancel_backend() to cancel the query at the database level.
    """
    user_id = session.get("user_id", "unknown")
    
    # Check if query exists
    query_info = query_tracker.get_query_info(request_id)
    if not query_info:
        raise APIException(
            code=ErrorCode.QUERY_CANCELLED,
            message=f"Query {request_id} not found or already completed",
            category=ErrorCategory.VALIDATION,
            status_code=404,
        )

    # Cancel the query
    success = await query_tracker.cancel_query(request_id, user_id)
    
    if not success:
        raise APIException(
            code=ErrorCode.QUERY_CANCELLED,
            message=f"Failed to cancel query {request_id}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        )

    logger.info(
        f"Query {request_id[:8]}... cancelled by user {user_id}",
        extra={
            "event": "query_cancelled",
            "request_id": request_id,
            "user_id": user_id,
            "reason": request.reason,
        },
    )

    return QueryCancelResponse(cancelled=True, request_id=request_id)
