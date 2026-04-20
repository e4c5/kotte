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


async def _collect_stream_chunks(
    *,
    request_id: str,
    exec_side_effect,
    max_rows: int,
    chunk_size: int,
):
    """Drive ``stream_query_results`` against a mocked DB and collect parsed chunks.

    Centralises the ``MagicMock`` wiring + ``settings.query_max_result_rows``
    patch + async iteration that every cap-related test would otherwise repeat.
    Returns the parsed NDJSON chunks alongside the mock so callers can also
    inspect ``execute_cypher.await_args_list`` (e.g. to assert probe calls).
    """
    mock_db = _stream_mock_db(exec_side_effect)
    query_tracker.unregister_query(request_id)

    chunks: list[dict] = []
    with patch.object(settings, "query_max_result_rows", max_rows):
        async for ch in stream_query_results(
            graph_name="test_graph",
            cypher_query="MATCH (n) RETURN n",
            chunk_size=chunk_size,
            offset=0,
            db_conn=mock_db,
            request_id=request_id,
            params={},
        ):
            chunks.append(json.loads(ch))
    return chunks, mock_db


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
    """Chunks never exceed remaining budget; cap reached yields QUERY_VALIDATION_ERROR line.

    The streaming loop probes for one extra row after hitting the cap so it can
    distinguish "user got everything and it happened to equal max_rows" from
    "we truncated". This test exercises the truncation branch: the probe must
    see at least one row beyond the cap for the error chunk to fire.
    """

    def exec_side_effect(_graph, cypher_query, params=None, **_kwargs):
        if "$__skip" not in cypher_query or "$__limit" not in cypher_query:
            return []
        skip = params.get("__skip")
        limit = params.get("__limit")
        if skip == 0 and limit == 5:
            return [{"x": i} for i in range(5)]
        if skip == 5 and limit == 1:
            return [{"x": 5}]
        return []

    chunks, _mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-cap",
        exec_side_effect=exec_side_effect,
        max_rows=5,
        chunk_size=100,
    )

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 5
    errs = [c for c in chunks if "error" in c]
    assert len(errs) == 1
    assert errs[0]["error"]["code"] == "QUERY_VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_stream_query_no_cap_warning_when_results_exactly_match_max_rows():
    """If the user happens to have exactly max_rows of data and nothing more,
    the probe should come back empty and NO cap-warning chunk must be emitted.
    Anything else would tell the UI 'we truncated your data' when we did not.
    """

    def exec_side_effect(_graph, cypher_query, params=None, **_kwargs):
        if "$__skip" not in cypher_query or "$__limit" not in cypher_query:
            return []
        skip = params.get("__skip")
        limit = params.get("__limit")
        if skip == 0 and limit == 5:
            return [{"x": i} for i in range(5)]
        return []

    chunks, mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-exact",
        exec_side_effect=exec_side_effect,
        max_rows=5,
        chunk_size=100,
    )

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 5
    errs = [c for c in chunks if "error" in c]
    assert errs == [], f"expected no cap warning, got {errs}"
    probe_calls = [
        call
        for call in mock_db.execute_cypher.await_args_list
        if call.kwargs.get("params", {}).get("__limit") == 1
    ]
    assert len(probe_calls) == 1, "exactly one 1-row probe should have happened"


@pytest.mark.asyncio
async def test_stream_query_multi_chunk_then_cap_error():
    """Several full pages then a partial fetch up to max_rows, then error NDJSON.

    Like the cap test above, the probe must see at least one row beyond the
    cap for the error chunk to fire. We mock that probe explicitly here.
    """

    def exec_side_effect(_graph, cypher_query, params=None, **_kwargs):
        if "$__skip" not in cypher_query or "$__limit" not in cypher_query:
            return []

        skip = params.get("__skip")
        limit = params.get("__limit")
        if (skip, limit) in [(0, 40), (40, 40)]:
            return [{"i": i} for i in range(40)]
        if (skip, limit) == (80, 20):
            return [{"i": i} for i in range(20)]
        if (skip, limit) == (100, 1):
            return [{"i": 100}]
        return []

    chunks, _mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-multi",
        exec_side_effect=exec_side_effect,
        max_rows=100,
        chunk_size=40,
    )

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 100
    errs = [c for c in chunks if "error" in c]
    assert len(errs) == 1
