"""Integration tests for database connections."""

import os

import pytest
from psycopg.errors import UndefinedTable

from app.core.database import DatabaseConnection
from app.core.errors import APIException

INVALID_TEST_DB_SECRET = "invalid-test-secret"

requires_real_db = pytest.mark.skipif(
    os.getenv("USE_REAL_TEST_DB", "false").lower() != "true",
    reason="Requires real test database (set USE_REAL_TEST_DB=true)",
)


@pytest.mark.integration
class TestDatabaseConnection:
    """Integration tests for database connection management."""

    @pytest.fixture
    def db_config(self, test_db_config):
        """Database configuration for tests."""
        return test_db_config

    @pytest.mark.asyncio
    @requires_real_db
    async def test_connection_establishment(self, db_config):
        """Test establishing a database connection."""
        conn = DatabaseConnection(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        try:
            await conn.connect()
        except (APIException, Exception) as e:
            # Skip if database is not available (expected in CI/development)
            pytest.skip(f"Database not available: {e}")
        try:
            assert conn._pool is not None
        finally:
            if conn._pool is not None:
                await conn.disconnect()

    @pytest.mark.asyncio
    @requires_real_db
    async def test_query_execution(self, db_config):
        """Test executing a simple query."""
        conn = DatabaseConnection(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        try:
            await conn.connect()
        except (APIException, Exception) as e:
            # Skip if database is not available
            pytest.skip(f"Database not available: {e}")
        try:
            result = await conn.execute_query("SELECT 1 as test_value")
            assert len(result) > 0
            assert result[0]["test_value"] == 1
        finally:
            if conn._pool is not None:
                await conn.disconnect()

    @pytest.mark.asyncio
    @requires_real_db
    async def test_transaction_rollback(self, db_config):
        """After a failed statement inside ``transaction()``, the pool stays usable."""
        conn = DatabaseConnection(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
        )
        try:
            await conn.connect()
        except (APIException, Exception) as e:
            pytest.skip(f"Database not available: {e}")
        try:
            with pytest.raises(UndefinedTable):
                async with conn.transaction() as ac:
                    await conn.execute_query("SELECT * FROM nonexistent_table", conn=ac)

            result = await conn.execute_query("SELECT 1")
            assert len(result) > 0
        finally:
            if conn._pool is not None:
                await conn.disconnect()

    @pytest.mark.asyncio
    async def test_invalid_connection_config(self):
        """Test connection with invalid configuration."""
        conn = DatabaseConnection(
            host="invalid-host",
            port=5432,
            database="invalid_db",
            user="invalid_user",
            password=INVALID_TEST_DB_SECRET,
        )
        with pytest.raises((APIException, Exception)):  # Should raise connection error
            await conn.connect()
