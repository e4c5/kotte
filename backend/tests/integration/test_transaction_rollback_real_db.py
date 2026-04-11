"""Optional integration test: transactional execute_query(..., conn=conn) rollback behavior.

Requires PostgreSQL reachable with the same settings as other real-DB tests.
Set USE_REAL_TEST_DB=true and ensure the DB has Apache AGE (same as app.connect).
"""

import os

import pytest
from psycopg.errors import UndefinedTable

from app.core.database import DatabaseConnection
from app.core.errors import APIException

requires_real_db = pytest.mark.skipif(
    os.getenv("USE_REAL_TEST_DB", "false").lower() != "true",
    reason="Requires real test database (set USE_REAL_TEST_DB=true)",
)

@pytest.mark.integration
@pytest.mark.asyncio
@requires_real_db
async def test_failed_query_in_transaction_does_not_poison_pool(test_db_config):
    """
    If a statement fails inside ``async with db.transaction() as conn``, the
    connection pool must still return a working connection afterward.

    Uses the same connection for success + failing ``execute_query`` (``conn=``)
    as production code paths.
    """
    db = DatabaseConnection(
        host=test_db_config["host"],
        port=test_db_config["port"],
        database=test_db_config["database"],
        user=test_db_config["user"],
        password=test_db_config["password"],
    )
    try:
        await db.connect()
    except APIException as e:
        pytest.skip(f"Database not available: {e}")

    try:
        with pytest.raises(UndefinedTable):
            async with db.transaction() as conn:
                await db.execute_query("SELECT 1 AS ok", conn=conn)
                await db.execute_query(
                    "SELECT * FROM kotte_tx_test_missing_7d4e9c2a",
                    conn=conn,
                )

        scalar = await db.execute_scalar("SELECT 1 AS v")
        assert scalar == 1
    finally:
        await db.disconnect()
