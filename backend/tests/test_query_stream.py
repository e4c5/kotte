"""Tests for query streaming behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.query_stream import stream_query_results
from app.core.config import settings
from app.services.query_tracker import query_tracker


def _stream_mock_db(exec_side_effect):
    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.execute_cypher = AsyncMock(side_effect=exec_side_effect)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=object())
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_db.connection = MagicMock(return_value=mock_cm)
    mock_db.get_backend_pid = AsyncMock(return_value=None)
    return mock_db


@pytest.mark.asyncio
async def test_stream_query_unregisters_tracker_on_completion():
    """Tracked streaming query should always be unregistered when stream completes."""
    request_id = "stream-test-request"

    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.execute_cypher = AsyncMock(return_value=[])

    query_tracker.unregister_query(request_id)
    query_tracker.register_query(
        request_id=request_id,
        db_conn=mock_db,
        query_text="MATCH (n) RETURN n",
        user_id="test-user",
    )

    chunks = []
    async for chunk in stream_query_results(
        graph_name="test_graph",
        cypher_query="MATCH (n) RETURN n",
        chunk_size=100,
        offset=0,
        db_conn=mock_db,
        request_id=request_id,
        params={},
    ):
        chunks.append(chunk)

    assert len(chunks) == 1
    assert query_tracker.get_query_info(request_id) is None


@pytest.mark.asyncio
async def test_stream_query_with_existing_limit_is_chunked_in_memory():
    """Queries that already contain LIMIT should still stream as multiple chunks."""
    request_id = "stream-existing-limit"

    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.execute_cypher = AsyncMock(
        return_value=[
            {"result": {"id": 1, "label": "Person", "properties": {}}},
            {"result": {"id": 2, "label": "Person", "properties": {}}},
            {"result": {"id": 3, "label": "Person", "properties": {}}},
        ]
    )

    chunks = []
    async for chunk in stream_query_results(
        graph_name="test_graph",
        cypher_query="MATCH (n) RETURN n LIMIT 3",
        chunk_size=2,
        offset=0,
        db_conn=mock_db,
        request_id=request_id,
        params={},
    ):
        chunks.append(json.loads(chunk))

    data_chunks = [c for c in chunks if "rows" in c]
    assert len(data_chunks) == 2
    assert data_chunks[0]["chunk_size"] == 2
    assert data_chunks[1]["chunk_size"] == 1
    mock_db.execute_cypher.assert_called_once()


@pytest.mark.asyncio
async def test_stream_query_empty_params_dict_reaches_execute_cypher():
    """Explicit {} must be passed to execute_cypher (3-arg cypher), not coerced to None."""
    request_id = "stream-empty-params"
    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.execute_cypher = AsyncMock(return_value=[])

    query_tracker.unregister_query(request_id)
    query_tracker.register_query(
        request_id=request_id,
        db_conn=mock_db,
        query_text="RETURN 1 AS x",
        user_id="test-user",
    )

    ndjson_lines = 0
    async for _chunk in stream_query_results(
        graph_name="test_graph",
        cypher_query="RETURN 1 AS x LIMIT 1",
        chunk_size=100,
        offset=0,
        db_conn=mock_db,
        request_id=request_id,
        params={},
    ):
        ndjson_lines += 1

    assert ndjson_lines == 0
    assert mock_db.execute_cypher.call_args.kwargs["params"] == {}


@pytest.mark.asyncio
async def test_stream_query_respects_max_rows_and_emits_error_line():
    """Chunks never exceed remaining budget; cap reached yields QUERY_VALIDATION_ERROR line."""
    request_id = "stream-max-rows-cap"

    def exec_side_effect(_graph, cypher_query, params=None, **_kwargs):
        if "$__skip" in cypher_query and "$__limit" in cypher_query:
            skip = params.get("__skip")
            limit = params.get("__limit")
            if skip == 0 and limit == 5:
                return [{"x": i} for i in range(5)]
        return []

    mock_db = _stream_mock_db(exec_side_effect)
    query_tracker.unregister_query(request_id)

    with patch.object(settings, "query_max_result_rows", 5):
        chunks = []
        async for ch in stream_query_results(
            graph_name="test_graph",
            cypher_query="MATCH (n) RETURN n",
            chunk_size=100,
            offset=0,
            db_conn=mock_db,
            request_id=request_id,
            params={},
        ):
            chunks.append(json.loads(ch))

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 5
    errs = [c for c in chunks if "error" in c]
    assert len(errs) == 1
    assert errs[0]["error"]["code"] == "QUERY_VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_stream_query_multi_chunk_then_cap_error():
    """Several full pages then a partial fetch up to max_rows, then error NDJSON."""
    request_id = "stream-max-rows-multi"

    def exec_side_effect(_graph, cypher_query, params=None, **_kwargs):
        if "$__skip" not in cypher_query or "$__limit" not in cypher_query:
            return []
        
        skip = params.get("__skip")
        limit = params.get("__limit")
        # Returns 40, then 40, then 20 = 100 total
        if (skip, limit) in [(0, 40), (40, 40)]:
            return [{"i": i} for i in range(40)]
        if (skip, limit) == (80, 20):
            return [{"i": i} for i in range(20)]
        return []

    mock_db = _stream_mock_db(exec_side_effect)
    query_tracker.unregister_query(request_id)

    with patch.object(settings, "query_max_result_rows", 100):
        chunks = []
        async for ch in stream_query_results(
            graph_name="test_graph",
            cypher_query="MATCH (n) RETURN n",
            chunk_size=40,
            offset=0,
            db_conn=mock_db,
            request_id=request_id,
            params={},
        ):
            chunks.append(json.loads(ch))

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 100
    errs = [c for c in chunks if "error" in c]
    assert len(errs) == 1
