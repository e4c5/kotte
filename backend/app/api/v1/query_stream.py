"""Query streaming endpoints for large result sets."""

import json
import logging
import uuid
from typing import Annotated, AsyncGenerator, Optional

import psycopg.errors
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.deps import get_session, get_db_connection
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
        validate_variable_length_traversal(cypher_query, settings.query_max_variable_hops)

        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{validated_graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )

        async with db_conn.connection() as exec_conn:
            # Safe mode: DB-level enforcement — mutations raise ReadOnlySqlTransaction (25006).
            if settings.query_safe_mode:
                await exec_conn.execute("SET TRANSACTION READ ONLY")

            try:
                backend_pid = await db_conn.get_backend_pid(conn=exec_conn)
                if backend_pid:
                    await query_tracker.set_backend_pid(request_id, backend_pid)
            except Exception as e:
                logger.warning("Failed to get backend PID for stream tracking: %s", e)

            # Use a psycopg server-side cursor to stream results without materialising
            # the full result set in Python memory.  Queries that already contain their
            # own LIMIT/SKIP are still streamed the same way — the server-side cursor
            # stops naturally when the Cypher engine stops producing rows.
            all_columns: Optional[list[str]] = None
            max_rows = settings.query_max_result_rows
            emitted_rows = 0
            current_offset = offset

            # cursor names must be unique within a connection; tie to request_id.
            cursor_name = f"kotte_stream_{request_id.replace('-', '_')}"

            async for raw_batch in db_conn.stream_cypher(
                validated_graph_name,
                cypher_query,
                chunk_size,
                cursor_name,
                exec_conn,
                params=params,
            ):
                remaining = max_rows - emitted_rows
                if remaining <= 0:
                    yield _stream_cap_error_chunk(max_rows)
                    return

                parsed_rows, chunk_columns = _parse_raw_rows(raw_batch)
                if all_columns is None:
                    all_columns = chunk_columns

                capped = parsed_rows[:remaining]
                emitted_rows += len(capped)
                # has_more=True only if this chunk was full AND we haven't hit the cap.
                has_more = (len(parsed_rows) == chunk_size) and (emitted_rows < max_rows)
                yield _chunk_to_ndjson(all_columns, capped, current_offset, has_more)
                current_offset += len(capped)

                # If the batch contained rows beyond the cap we know truncation happened
                # without needing to fetch the next batch.  For the edge case where a
                # full batch exactly fills the cap we rely on the next loop iteration:
                # if the cursor has more rows, remaining==0 triggers the error there;
                # if the cursor is exhausted the loop ends cleanly with no false positive.
                if len(parsed_rows) > len(capped):
                    yield _stream_cap_error_chunk(max_rows)
                    return

    except APIException:
        raise
    except psycopg.errors.ReadOnlySqlTransaction:
        error_chunk = {
            "error": {
                "code": ErrorCode.QUERY_VALIDATION_ERROR,
                "message": "Mutating queries are not allowed in safe mode",
            }
        }
        yield json.dumps(error_chunk) + "\n"
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
