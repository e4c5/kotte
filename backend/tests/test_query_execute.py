"""Unit tests for query execution endpoint logic."""

import pytest
import psycopg.errors
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.v1.query import execute_query
from app.core.config import settings
from app.core.errors import APIException, ErrorCode
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


@pytest.mark.asyncio
async def test_execute_query_safe_mode_rejects_mutation_via_read_only_transaction():
    """With query_safe_mode=True a ReadOnlySqlTransaction from PG must surface as 422."""
    exec_conn = AsyncMock()
    # Simulate PG rejecting the SET TRANSACTION READ ONLY path when the cypher writes data.
    exec_conn.execute = AsyncMock(
        side_effect=psycopg.errors.ReadOnlySqlTransaction("read-only transaction")
    )

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=exec_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_db = MagicMock()
    mock_db.execute_scalar = AsyncMock(return_value=1)
    mock_db.get_backend_pid = AsyncMock(return_value=None)
    mock_db.connection = MagicMock(return_value=mock_cm)
    mock_db.execute_cypher = AsyncMock(return_value=[])

    req = QueryExecuteRequest(
        graph="test_graph",
        cypher="CREATE (n:Person {name: 'Alice'})",
    )

    with patch.object(settings, "query_safe_mode", True):
        with pytest.raises(APIException) as exc_info:
            await execute_query(req, db_conn=mock_db, session={"user_id": "test-user"})

    assert exc_info.value.status_code == 422
    assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
    assert "safe mode" in exc_info.value.message
