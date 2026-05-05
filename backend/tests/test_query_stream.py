"""Tests for query streaming behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.query_stream import stream_query_results
from app.core.config import settings
from app.services.query_tracker import query_tracker


def _make_stream_gen(*batches):
    """Return a callable that yields the given batches as an async generator.

    Used to mock ``db_conn.stream_cypher``, which is a regular method that
    returns an async generator (not a coroutine).
    """

    async def _gen(*_args, **_kwargs):
        for batch in batches:
            yield batch

    return _gen


def _stream_mock_db(*batches):
    """Build a mock DatabaseConnection that streams the provided row batches."""
    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.stream_cypher = MagicMock(side_effect=_make_stream_gen(*batches))
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=object())
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_db.connection = MagicMock(return_value=mock_cm)
    mock_db.get_backend_pid = AsyncMock(return_value=None)
    return mock_db


async def _collect_stream_chunks(
    *,
    request_id: str,
    batches: list,
    max_rows: int,
    chunk_size: int,
):
    """Drive ``stream_query_results`` against a mocked DB and collect parsed chunks.

    Centralises the ``MagicMock`` wiring + ``settings.query_max_result_rows``
    patch + async iteration that every cap-related test would otherwise repeat.
    Returns the parsed NDJSON chunks alongside the mock so callers can also
    inspect ``stream_cypher.call_args_list``.
    """
    mock_db = _stream_mock_db(*batches)
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

    mock_db = _stream_mock_db()  # no batches → empty result

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

    # Empty cursor → no data chunks
    assert len(chunks) == 0
    assert query_tracker.get_query_info(request_id) is None


@pytest.mark.asyncio
async def test_stream_query_with_existing_limit_is_chunked_in_memory():
    """Queries with LIMIT still produce multiple NDJSON chunks (server-side cursor chunking)."""
    request_id = "stream-existing-limit"

    # Server-side cursor fetches chunk_size=2 at a time: two batches for 3 rows.
    batch1 = [
        {"result": {"id": 1, "label": "Person", "properties": {}}},
        {"result": {"id": 2, "label": "Person", "properties": {}}},
    ]
    batch2 = [
        {"result": {"id": 3, "label": "Person", "properties": {}}},
    ]
    mock_db = _stream_mock_db(batch1, batch2)

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
    mock_db.stream_cypher.assert_called_once()


@pytest.mark.asyncio
async def test_stream_query_empty_params_dict_reaches_stream_cypher():
    """Explicit {} must be forwarded to stream_cypher (3-arg cypher), not coerced to None."""
    request_id = "stream-empty-params"
    mock_db = _stream_mock_db()  # no batches

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
    assert mock_db.stream_cypher.call_args.kwargs["params"] == {}


@pytest.mark.asyncio
async def test_stream_query_respects_max_rows_and_emits_error_line():
    """Chunks never exceed remaining budget; cap reached yields QUERY_VALIDATION_ERROR line.

    When the first batch contains more rows than the cap allows, the excess is
    detected within that batch (no extra DB round-trip needed).
    """
    # One batch with more rows than max_rows=5.
    batch = [{"x": i} for i in range(6)]

    chunks, _mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-cap",
        batches=[batch],
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
    """If the user has exactly max_rows of data and the cursor is then exhausted,
    no cap-warning chunk must be emitted — no false positive.

    With server-side cursors the loop advances to the next batch after filling
    max_rows; if that next batch is empty (cursor exhausted), the remaining==0
    guard is never reached and no error is yielded.
    """
    # Exactly max_rows=5 rows split across two cursor batches (chunk_size=3).
    # The cursor returns empty on the third fetchmany → no truncation.
    chunks, _mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-exact",
        batches=[[{"x": i} for i in range(3)], [{"x": i} for i in range(3, 5)]],
        max_rows=5,
        chunk_size=3,
    )

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 5
    errs = [c for c in chunks if "error" in c]
    assert errs == [], f"expected no cap warning, got {errs}"


@pytest.mark.asyncio
async def test_stream_query_multi_chunk_then_cap_error():
    """Several full batches filling max_rows followed by another non-empty batch → error.

    Batches 1 and 2 each have 40 rows (max_rows=100, chunk_size=40).  Batch 3
    fills the remaining 20 but the cursor still has more rows (batch 4 is non-
    empty), so the remaining==0 guard fires on the 4th iteration and emits the
    QUERY_VALIDATION_ERROR line.
    """
    chunks, _mock_db = await _collect_stream_chunks(
        request_id="stream-max-rows-multi",
        batches=[
            [{"i": i} for i in range(40)],
            [{"i": i} for i in range(40, 80)],
            [{"i": i} for i in range(80, 100)],
            [{"i": 100}],  # one more row beyond the cap
        ],
        max_rows=100,
        chunk_size=40,
    )

    data_rows = sum(c.get("chunk_size", 0) for c in chunks if "rows" in c)
    assert data_rows == 100
    errs = [c for c in chunks if "error" in c]
    assert len(errs) == 1
