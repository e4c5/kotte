"""Unit tests for query execution endpoint logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.v1.query import execute_query
from app.core.config import settings
from app.models.query import QueryExecuteRequest


@pytest.mark.asyncio
async def test_execute_query_applies_visualization_limit_when_enabled():
    """for_visualization should execute a LIMIT-capped query when no LIMIT is present."""
    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)  # Graph exists
    mock_db.get_backend_pid = AsyncMock(return_value=12345)
    mock_db.execute_cypher = AsyncMock(return_value=[])

    req = QueryExecuteRequest(
        graph="test_graph",
        cypher="MATCH (n) RETURN n",
        params={},
        for_visualization=True,
    )

    response = await execute_query(req, db_conn=mock_db, session={"user_id": "test-user"})

    assert response.row_count == 0
    call_args = mock_db.execute_cypher.call_args
    assert call_args is not None
    executed_cypher = call_args.args[1]
    assert f"LIMIT {settings.max_nodes_for_graph}" in executed_cypher.upper()
