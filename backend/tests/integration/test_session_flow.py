"""Integration tests for session management flow."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


class TestSessionFlow:
    """Integration tests for session endpoints."""

    def test_connect_without_auth(self, client: TestClient):
        """Test connecting without authentication."""
        response = client.post(
            "/api/v1/session/connect",
            json={
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "test_db",
                    "user": "test_user",
                    "password": "test_password",
                }
            },
        )
        
        assert response.status_code == 401

    @patch('app.api.v1.session.DatabaseConnection')
    def test_connect_success(self, mock_db_class, authenticated_client: TestClient):
        """Test successful database connection."""
        # Mock database connection
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db_class.return_value = mock_db
        
        response = authenticated_client.post(
            "/api/v1/session/connect",
            json={
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "test_db",
                    "user": "test_user",
                    "password": "test_password",
                }
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["connected"] is True
        assert data["database"] == "test_db"
        assert data["host"] == "localhost"
        assert data["port"] == 5432
        
        # Verify connect was called
        mock_db.connect.assert_called_once()

    def test_status_without_connection(self, authenticated_client: TestClient):
        """Test status when not connected to database."""
        response = authenticated_client.get("/api/v1/session/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["database"] is None

    @patch('app.api.v1.session.DatabaseConnection')
    def test_status_with_connection(self, mock_db_class, authenticated_client: TestClient):
        """Test status when connected to database."""
        # Mock database connection
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db_class.return_value = mock_db
        
        # Connect
        connect_response = authenticated_client.post(
            "/api/v1/session/connect",
            json={
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "test_db",
                    "user": "test_user",
                    "password": "test_password",
                }
            },
        )
        assert connect_response.status_code == 201
        
        # Get status
        status_response = authenticated_client.get("/api/v1/session/status")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["connected"] is True
        assert data["database"] == "test_db"
        assert data["host"] == "localhost"
        assert data["port"] == 5432

    @patch('app.api.v1.session.DatabaseConnection')
    def test_disconnect(self, mock_db_class, authenticated_client: TestClient):
        """Test disconnecting from database."""
        # Mock database connection
        mock_db = MagicMock()
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()
        mock_db.is_connected = MagicMock(return_value=True)
        mock_db_class.return_value = mock_db
        
        # Connect first
        connect_response = authenticated_client.post(
            "/api/v1/session/connect",
            json={
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "test_db",
                    "user": "test_user",
                    "password": "test_password",
                }
            },
        )
        assert connect_response.status_code == 201
        
        # Disconnect
        disconnect_response = authenticated_client.post("/api/v1/session/disconnect")
        assert disconnect_response.status_code == 200
        data = disconnect_response.json()
        assert data["disconnected"] is True
        
        # Verify disconnect was called
        mock_db.disconnect.assert_called_once()
        
        # Verify status shows disconnected
        status_response = authenticated_client.get("/api/v1/session/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["connected"] is False

    def test_full_session_flow(self, authenticated_client: TestClient):
        """Test complete session flow."""
        with patch('app.api.v1.session.DatabaseConnection') as mock_db_class:
            mock_db = MagicMock()
            mock_db.connect = AsyncMock()
            mock_db.disconnect = AsyncMock()
            mock_db.is_connected = MagicMock(return_value=True)
            mock_db_class.return_value = mock_db
            
            # 1. Connect
            connect_response = authenticated_client.post(
                "/api/v1/session/connect",
                json={
                    "connection": {
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "user": "test_user",
                        "password": "test_password",
                    }
                },
            )
            assert connect_response.status_code == 201
            
            # 2. Check status
            status_response = authenticated_client.get("/api/v1/session/status")
            assert status_response.status_code == 200
            assert status_response.json()["connected"] is True
            
            # 3. Disconnect
            disconnect_response = authenticated_client.post("/api/v1/session/disconnect")
            assert disconnect_response.status_code == 200
            
            # 4. Verify disconnected
            status_response = authenticated_client.get("/api/v1/session/status")
            assert status_response.json()["connected"] is False

