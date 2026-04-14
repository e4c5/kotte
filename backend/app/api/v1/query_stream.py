"""Query streaming endpoints for large result sets."""

import json
import logging
import uuid
from typing import Annotated, AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.auth import get_session
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory, translate_db_error
from app.core.validation import (
    validate_graph_name,
    validate_query_length,
    validate_variable_length_traversal,
)
from app.models.query import QueryStreamChunk, QueryResultRow, QueryStreamRequest
from app.services.agtype import AgTypeParser
from app.services.query_tracker import query_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_raw_rows(raw_rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Parse agtype values and return parsed rows and sorted column names."""
    parsed_rows: list[dict] = []
    columns: set[str] = set()
    for raw_row in raw_rows:
        parsed_row: dict = {}
        for col_name, agtype_value in raw_row.items():
            columns.add(col_name)
            parsed_row[col_name] = AgTypeParser.parse(agtype_value)
        parsed_rows.append(parsed_row)
    return parsed_rows, sorted(columns)


def _chunk_to_ndjson(columns: list[str], rows: list[dict], offset: int, has_more: bool) -> str:
    """Build one NDJSON line for a stream chunk."""
    result_rows = [QueryResultRow(data=row) for row in rows]
    chunk = QueryStreamChunk(
        columns=columns,
        rows=result_rows,
        chunk_size=len(result_rows),
        offset=offset,
        has_more=has_more,
        total_rows=None,
    )
    return json.dumps(chunk.model_dump(), default=str) + "\n"


def _stream_cap_error_chunk(max_rows: int) -> str:
    """Return a standardized stream-cap error chunk as NDJSON."""
    error_chunk = {
        "error": {
            "code": ErrorCode.QUERY_VALIDATION_ERROR,
            "message": f"Stream result cap reached ({max_rows} rows). Refine query with WHERE/LIMIT.",
        }
    }
    return json.dumps(error_chunk) + "\n"


def _strip_trailing_semicolon(cypher_query: str) -> str:
    """Return Cypher text without trailing semicolon."""
    cypher_base = cypher_query.rstrip()
    if cypher_base.endswith(";"):
        return cypher_base[:-1].rstrip()
    return cypher_base


async def get_db_connection(session: Annotated[dict, Depends(get_session)]) -> DatabaseConnection:
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


async def stream_query_results(
    graph_name: str,
    cypher_query: str,
    chunk_size: int,
    offset: int,
    db_conn: DatabaseConnection,
    request_id: str,
    params: Optional[dict] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream query results in chunks.
    
    Yields JSON lines (NDJSON format) where each line is a JSON object
    representing a chunk of results.
    """
    try:
        # Validate graph name format (prevents SQL injection)
        validated_graph_name = validate_graph_name(graph_name)
        
        # Validate query length
        validate_query_length(cypher_query)
        validate_variable_length_traversal(
            cypher_query, settings.query_max_variable_hops
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

        async with db_conn.connection() as exec_conn:
            try:
                backend_pid = await db_conn.get_backend_pid(conn=exec_conn)
                if backend_pid:
                    await query_tracker.set_backend_pid(request_id, backend_pid)
            except Exception as e:
                logger.warning("Failed to get backend PID for stream tracking: %s", e)

            # Pass params through unchanged: None → 2-arg cypher(); {} or non-empty → 3-arg
            # (CypherExecutor uses `params is not None`, not truthiness.)

            # Build SQL query with LIMIT and OFFSET for pagination
            # Note: We need to wrap the original query in a subquery to add LIMIT/OFFSET
            # This is a simplified approach - for complex queries, we might need to parse the Cypher
            # and inject LIMIT/OFFSET at the Cypher level
            # For now, we'll use a cursor-based approach by modifying the Cypher query
            # to add LIMIT and SKIP clauses

            # Check if query already has LIMIT/SKIP
            cypher_upper = cypher_query.upper()
            has_limit = "LIMIT" in cypher_upper
            has_skip = "SKIP" in cypher_upper or "OFFSET" in cypher_upper

            # We'll stream by fetching chunks with LIMIT/SKIP and enforce a max result cap.
            current_offset = offset
            all_columns = None
            max_rows = settings.query_max_result_rows
            emitted_rows = 0

            if has_limit or has_skip:
                # Query already controls result window; execute once and stream in-memory chunks.
                # The full LIMIT/SKIP window is materialized before chunking (large LIMIT values
                # can still use significant RAM). Prefer unpaginated Cypher plus this endpoint's
                # SKIP/LIMIT loop for very large scans.
                # Ignore request offset here to avoid double-applying SKIP/OFFSET.
                stream_offset = 0
                raw_rows = await db_conn.execute_cypher(
                    validated_graph_name,
                    cypher_query,
                    params=params,
                    time_limit_seconds=settings.query_timeout,
                    conn=exec_conn,
                )

                parsed_rows, all_columns = _parse_raw_rows(raw_rows)
                capped_rows = parsed_rows[stream_offset : stream_offset + max_rows]
                for start in range(0, len(capped_rows), chunk_size):
                    chunk_rows = capped_rows[start : start + chunk_size]
                    has_more = start + chunk_size < len(capped_rows)
                    yield _chunk_to_ndjson(all_columns, chunk_rows, stream_offset + start, has_more)

                if len(parsed_rows) - stream_offset > max_rows:
                    yield _stream_cap_error_chunk(max_rows)
                return

            while True:
                remaining = max_rows - emitted_rows
                if remaining <= 0:
                    return

                # Add SKIP and LIMIT to the query (strip trailing ; so we don't produce "...; SKIP")
                cypher_base = _strip_trailing_semicolon(cypher_query)
                fetch_limit = min(chunk_size, remaining)
                modified_cypher = f"{cypher_base} SKIP {current_offset} LIMIT {fetch_limit}"

                # Execute via literal SQL (execute_cypher) to avoid cypher() overload issues
                raw_rows = await db_conn.execute_cypher(
                    validated_graph_name,
                    modified_cypher,
                    params=params,
                    time_limit_seconds=settings.query_timeout,
                    conn=exec_conn,
                )

                # Parse agtype results
                parsed_rows, chunk_columns = _parse_raw_rows(raw_rows)

                # Set columns from first chunk
                if all_columns is None:
                    all_columns = chunk_columns

                # Convert to QueryResultRow format
                n = len(parsed_rows)
                chunk_emitted_after = emitted_rows + n
                has_more = (n == fetch_limit) and (chunk_emitted_after < max_rows)

                # Yield chunk as JSON line
                yield _chunk_to_ndjson(all_columns, parsed_rows, current_offset, has_more)
                emitted_rows += n

                if emitted_rows >= max_rows:
                    if n == fetch_limit:  # Check if there might be more rows beyond the cap
                        yield _stream_cap_error_chunk(max_rows)
                    return

                if n < fetch_limit:
                    break

                current_offset += fetch_limit

                # Safety fallback
                if current_offset >= 1_000_000:
                    logger.warning(
                        f"Streaming stopped at {current_offset} rows (safety limit)"
                    )
                    break

    except APIException:
        raise
    except Exception as e:
        logger.exception("Error streaming query results", extra={"error": str(e)})
        api_exc = translate_db_error(
            e,
            context={"graph": graph_name, "query": cypher_query[:200]},
        )
        code = api_exc.code if api_exc else ErrorCode.QUERY_EXECUTION_ERROR
        message = api_exc.message if api_exc else f"Failed to stream results: {str(e)}"
        error_chunk = {"error": {"code": code, "message": message}}
        yield json.dumps(error_chunk) + "\n"
        # End generator cleanly; client has received the error in the stream
    finally:
        query_tracker.unregister_query(request_id)


@router.post("/stream")
async def stream_query(
    request: QueryStreamRequest,
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
    session: Annotated[dict, Depends(get_session)],
) -> StreamingResponse:
    """
    Stream query results in chunks (NDJSON format).
    
    Returns a streaming response where each line is a JSON object containing
    a chunk of results. Use this endpoint for large result sets that would
    be too large to load into memory at once.
    
    Example response format (NDJSON):
    {"columns": ["name", "age"], "rows": [{"data": {"name": "Alice", "age": 30}}], "chunk_size": 1, "offset": 0, "has_more": true}
    {"columns": ["name", "age"], "rows": [{"data": {"name": "Bob", "age": 25}}], "chunk_size": 1, "offset": 1, "has_more": false}
    """
    request_id = str(uuid.uuid4())
    user_id = session.get("user_id", "unknown")
    
    # Register query for cancellation tracking
    query_tracker.register_query(
        request_id=request_id,
        db_conn=db_conn,
        query_text=request.cypher[:200],
        user_id=user_id,
    )

    # Create streaming response
    return StreamingResponse(
        stream_query_results(
            graph_name=request.graph,
            cypher_query=request.cypher,
            chunk_size=request.chunk_size,
            offset=request.offset,
            db_conn=db_conn,
            request_id=request_id,
            params=request.params,
        ),
        media_type="application/x-ndjson",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
