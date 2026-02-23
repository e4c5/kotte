"""Tests for query streaming behavior."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.query_stream import stream_query_results
from app.services.query_tracker import query_tracker


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
        params={},
        chunk_size=100,
        offset=0,
        db_conn=mock_db,
        request_id=request_id,
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
        params={},
        chunk_size=2,
        offset=0,
        db_conn=mock_db,
        request_id=request_id,
    ):
        chunks.append(json.loads(chunk))

    data_chunks = [c for c in chunks if "rows" in c]
    assert len(data_chunks) == 2
    assert data_chunks[0]["chunk_size"] == 2
    assert data_chunks[1]["chunk_size"] == 1
    mock_db.execute_cypher.assert_called_once()
