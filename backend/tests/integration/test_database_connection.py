"""Integration tests for database connections."""

import pytest
from app.core.database import DatabaseConnection
from app.core.errors import APIException


@pytest.mark.integration
class TestDatabaseConnection:
    """Integration tests for database connection management."""

    @pytest.fixture
    def db_config(self, test_db_config):
        """Database configuration for tests."""
        return test_db_config

    @pytest.mark.asyncio
    async def test_connection_establishment(self, db_config):
        """Test establishing a database connection."""
        conn = DatabaseConnection(db_config)
        try:
            await conn.connect()
            assert conn.is_connected()
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_query_execution(self, db_config):
        """Test executing a simple query."""
        conn = DatabaseConnection(db_config)
        try:
            await conn.connect()
            result = await conn.execute_query("SELECT 1 as test_value")
            assert len(result) > 0
            assert result[0]["test_value"] == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_config):
        """Test transaction rollback."""
        conn = DatabaseConnection(db_config)
        try:
            await conn.connect()
            await conn.begin_transaction()
            
            # Execute a query that would fail
            try:
                await conn.execute_query("SELECT * FROM nonexistent_table")
            except Exception:
                pass
            
            await conn.rollback_transaction()
            
            # Connection should still be usable
            result = await conn.execute_query("SELECT 1")
            assert len(result) > 0
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_invalid_connection_config(self):
        """Test connection with invalid configuration."""
        invalid_config = {
            "host": "invalid-host",
            "port": 5432,
            "database": "invalid_db",
            "user": "invalid_user",
            "password": "invalid_password",
        }
        
        conn = DatabaseConnection(invalid_config)
        with pytest.raises(Exception):  # Should raise connection error
            await conn.connect()

