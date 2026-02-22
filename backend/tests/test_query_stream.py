"""Tests for query streaming behavior."""

import pytest
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
