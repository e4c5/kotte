"""Integration tests for saved connections endpoints."""

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


class TestSavedConnections:
    """Integration tests for saved connection endpoints."""

    @pytest.mark.asyncio
    async def test_save_connection_without_auth(self, async_client: httpx.AsyncClient):
        """Test saving connection without authentication."""
        response = await async_client.post(
            "/api/v1/connections",
            json={
                "name": "Test Connection",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_save_connection_success(self, authenticated_client: httpx.AsyncClient):
        """Test successfully saving a connection."""
        import uuid
        unique_name = f"Test Connection {uuid.uuid4().hex[:8]}"
        response = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": unique_name,
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == unique_name
        assert data["host"] == "localhost"
        assert data["port"] == 5432
        assert data["database"] == "test_db"
        # Credentials should NOT be in response
        assert "username" not in data
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_save_connection_duplicate_name(self, authenticated_client: httpx.AsyncClient):
        """Test saving connection with duplicate name."""
        import uuid
        unique_name = f"Duplicate Test {uuid.uuid4().hex[:8]}"
        # Save first connection
        response1 = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": unique_name,
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        assert response1.status_code == 201
        
        # Try to save another with same name
        response2 = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": unique_name,
                "host": "localhost",
                "port": 5433,
                "database": "test_db2",
                "username": "test_user2",
                "password": "test_password2",
            },
        )
        
        assert response2.status_code == 422
        data = response2.json()
        assert "error" in data
        assert "already exists" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_list_connections(self, authenticated_client: httpx.AsyncClient):
        """Test listing saved connections."""
        import uuid
        unique_name = f"List Test Connection {uuid.uuid4().hex[:8]}"
        # Save a connection first
        save_response = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": unique_name,
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        assert save_response.status_code == 201
        
        # List connections
        list_response = await authenticated_client.get("/api/v1/connections")
        
        assert list_response.status_code == 200
        data = list_response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify no credentials in list
        for conn in data:
            assert "username" not in conn
            assert "password" not in conn
            assert "id" in conn
            assert "name" in conn

    @pytest.mark.asyncio
    async def test_get_connection(self, authenticated_client: httpx.AsyncClient):
        """Test getting a saved connection with credentials."""
        import uuid
        unique_name = f"Get Test Connection {uuid.uuid4().hex[:8]}"
        # Save a connection first
        save_response = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": unique_name,
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        assert save_response.status_code == 201
        connection_id = save_response.json()["id"]
        
        # Get the connection
        get_response = await authenticated_client.get(f"/api/v1/connections/{connection_id}")
        
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["id"] == connection_id
        assert data["name"] == unique_name
        # Credentials should be present (decrypted) for connection use
        assert "username" in data
        assert "password" in data
        assert data["username"] == "test_user"
        assert data["password"] == "test_password"

    @pytest.mark.asyncio
    async def test_get_connection_not_found(self, authenticated_client: httpx.AsyncClient):
        """Test getting non-existent connection."""
        response = await authenticated_client.get("/api/v1/connections/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_delete_connection(self, authenticated_client: httpx.AsyncClient):
        """Test deleting a saved connection."""
        # Save a connection first
        save_response = await authenticated_client.post(
            "/api/v1/connections",
            json={
                "name": "Delete Test Connection",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "username": "test_user",
                "password": "test_password",
            },
        )
        assert save_response.status_code == 201
        connection_id = save_response.json()["id"]
        
        # Delete the connection
        delete_response = await authenticated_client.delete(f"/api/v1/connections/{connection_id}")
        
        assert delete_response.status_code == 204
        
        # Verify it's deleted
        get_response = await authenticated_client.get(f"/api/v1/connections/{connection_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_connection_not_found(self, authenticated_client: httpx.AsyncClient):
        """Test deleting non-existent connection."""
        response = await authenticated_client.delete("/api/v1/connections/nonexistent-id")
        
        assert response.status_code == 404

