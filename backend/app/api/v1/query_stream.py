"""Query streaming endpoints for large result sets."""

import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.auth import get_session
from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import validate_graph_name, validate_query_length
from app.models.query import QueryStreamChunk, QueryResultRow, QueryStreamRequest
from app.services.agtype import AgTypeParser
from app.services.query_tracker import query_tracker

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


async def stream_query_results(
    graph_name: str,
    cypher_query: str,
    params: dict,
    chunk_size: int,
    offset: int,
    db_conn: DatabaseConnection,
    request_id: str,
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
        
        cypher_params = params or {}
        has_params = bool(cypher_params)
        
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
        
        # If query doesn't have LIMIT, we'll add it
        # We'll stream by fetching chunks with LIMIT and SKIP
        current_offset = offset
        all_columns = None
        total_rows_estimated = None
        
        while True:
            # Build Cypher query with LIMIT and SKIP
            if has_limit or has_skip:
                # If query already has LIMIT/SKIP, we can't easily paginate
                # For now, execute as-is and return all results in one chunk
                modified_cypher = cypher_query
                is_final_chunk = True
            else:
                # Add SKIP and LIMIT to the query
                # Simple approach: append to the end (works for most queries)
                modified_cypher = f"{cypher_query.rstrip(';')} SKIP {current_offset} LIMIT {chunk_size}"
                is_final_chunk = False
            
            # Execute via literal SQL (execute_cypher) to avoid cypher() overload issues
            raw_rows = await db_conn.execute_cypher(
                validated_graph_name,
                modified_cypher,
                params=cypher_params if has_params else None,
                timeout=settings.query_timeout,
            )
            
            # Parse agtype results
            parsed_rows = []
            chunk_columns = set()
            
            for raw_row in raw_rows:
                parsed_row = {}
                for col_name, agtype_value in raw_row.items():
                    chunk_columns.add(col_name)
                    parsed_value = AgTypeParser.parse(agtype_value)
                    parsed_row[col_name] = parsed_value
                parsed_rows.append(parsed_row)
            
            # Set columns from first chunk
            if all_columns is None:
                all_columns = sorted(list(chunk_columns))
            
            # Convert to QueryResultRow format
            result_rows = [
                QueryResultRow(data=row) for row in parsed_rows
            ]
            
            # Determine if there are more rows
            has_more = len(parsed_rows) == chunk_size and not is_final_chunk
            
            # Create chunk response
            chunk = QueryStreamChunk(
                columns=all_columns,
                rows=result_rows,
                chunk_size=len(result_rows),
                offset=current_offset,
                has_more=has_more,
                total_rows=None,  # We don't know total without COUNT query
            )
            
            # Yield chunk as JSON line
            yield json.dumps(chunk.model_dump(), default=str) + "\n"
            
            # If this was the last chunk or we got fewer rows than requested, we're done
            if not has_more or len(parsed_rows) < chunk_size:
                break
            
            # Move to next chunk
            current_offset += chunk_size
            
            # Safety limit: don't stream more than 1M rows total
            if current_offset >= 1_000_000:
                logger.warning(f"Streaming stopped at {current_offset} rows (safety limit)")
                break
    
    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error streaming query results: {e}")
        # Send error as final chunk
        error_chunk = {
            "error": {
                "code": ErrorCode.QUERY_EXECUTION_ERROR,
                "message": f"Failed to stream results: {str(e)}",
            }
        }
        yield json.dumps(error_chunk) + "\n"
        raise


@router.post("/stream")
async def stream_query(
    request: QueryStreamRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
    session: dict = Depends(get_session),
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
    
    try:
        # Get backend PID for cancellation
        backend_pid = await db_conn.get_backend_pid()
        if backend_pid:
            await query_tracker.set_backend_pid(request_id, backend_pid)
    except Exception as e:
        logger.warning(f"Failed to get backend PID for query tracking: {e}")
    
    # Create streaming response
    return StreamingResponse(
        stream_query_results(
            graph_name=request.graph,
            cypher_query=request.cypher,
            params=request.params or {},
            chunk_size=request.chunk_size,
            offset=request.offset,
            db_conn=db_conn,
            request_id=request_id,
        ),
        media_type="application/x-ndjson",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

