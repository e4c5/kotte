"""Pytest configuration and fixtures."""

import sys

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def test_app(monkeypatch):
    """
    Create FastAPI app with middleware suitable for testing.
    CSRF and rate limiting disabled so auth/session tests can run.
    """
    monkeypatch.setenv("CSRF_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-for-unit-tests")
    monkeypatch.setenv("ENVIRONMENT", "test")
    for mod in ("app.core.config", "app.main"):
        if mod in sys.modules:
            del sys.modules[mod]
    from app.main import create_app
    return create_app()


@pytest.fixture
def client(test_app):
    """Test client for FastAPI app (uses test_app with session support)."""
    return TestClient(test_app, base_url="http://testserver")


@pytest.fixture(autouse=True)
def cleanup_sessions():
    """Clean up sessions after each test to avoid state leakage."""
    yield
    from app.core.auth import session_manager
    session_manager._sessions.clear()


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

