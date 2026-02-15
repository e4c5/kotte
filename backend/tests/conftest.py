"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock

from app.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    mock_conn = Mock()
    mock_conn.execute = AsyncMock(return_value=[])
    mock_conn.fetchall = AsyncMock(return_value=[])
    mock_conn.fetchone = AsyncMock(return_value=None)
    return mock_conn


@pytest.fixture
def mock_session():
    """Mock session for testing."""
    return {
        "session_id": "test-session-id",
        "user_id": "test-user-id",
        "connection_config": {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password",
        },
    }

