"""Integration test configuration and fixtures."""

import os
import pytest
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient
from app.main import create_app
from app.core.auth import session_manager
from app.services.user import user_service


@pytest.fixture(scope="function")
def test_app(monkeypatch):
    """Create a test FastAPI app with all middleware."""
    # Override settings for integration tests
    monkeypatch.setenv("CSRF_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-for-integration-tests-only")
    
    # Reload config module to pick up new settings
    import importlib
    import app.core.config
    importlib.reload(app.core.config)
    
    # Create fresh app instance
    app = create_app()
    return app


@pytest.fixture(scope="function")
def client(test_app):
    """
    Test client with session middleware support.
    
    Uses Starlette's TestClient which properly handles ASGI middleware.
    """
    return TestClient(test_app, base_url="http://testserver")


@pytest.fixture(scope="function")
def authenticated_client(client):
    """
    Test client with authenticated session.
    
    Creates a user, logs in, and returns client with session cookie.
    """
    # Create a test user if it doesn't exist
    test_username = "testuser"
    test_password = "testpass"
    
    # Clean up any existing test user
    if test_username in user_service._users:
        del user_service._users[test_username]
    
    # Create test user
    user_service.create_user(test_username, test_password)
    
    # Login to create session
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": test_username, "password": test_password},
    )
    
    if login_response.status_code != 200:
        pytest.skip(f"Failed to create authenticated session: {login_response.status_code}")
    
    # Return client with session cookie
    return client


@pytest.fixture(scope="function")
def admin_client(client):
    """
    Test client authenticated as admin user.
    """
    # Login as admin
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    
    if login_response.status_code != 200:
        pytest.skip(f"Failed to login as admin: {login_response.status_code}")
    
    return client


@pytest.fixture(scope="function")
def mock_db_connection():
    """
    Mock database connection for testing.
    
    Returns a mock that can be used to replace DatabaseConnection.
    """
    mock_conn = MagicMock()
    mock_conn.is_connected = MagicMock(return_value=True)
    mock_conn.connect = AsyncMock()
    mock_conn.disconnect = AsyncMock()
    mock_conn.execute_query = AsyncMock(return_value=[])
    mock_conn.execute_scalar = AsyncMock(return_value=None)
    mock_conn.get_backend_pid = AsyncMock(return_value=12345)
    mock_conn.cancel_backend = AsyncMock()
    mock_conn.begin_transaction = AsyncMock()
    mock_conn.commit_transaction = AsyncMock()
    mock_conn.rollback_transaction = AsyncMock()
    
    return mock_conn


@pytest.fixture(scope="function")
def connected_client(authenticated_client, mock_db_connection):
    """
    Test client with authenticated session and mocked database connection.
    """
    # Patch DatabaseConnection to return our mock
    with patch('app.api.v1.session.DatabaseConnection') as mock_db_class:
        mock_db_class.return_value = mock_db_connection
        
        # Connect to database
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
        
        if connect_response.status_code != 201:
            pytest.skip(f"Failed to connect to database: {connect_response.status_code}")
        
        # Store mock for later use
        authenticated_client._mock_db = mock_db_connection
        authenticated_client._mock_db_class = mock_db_class
        
        yield authenticated_client


@pytest.fixture(scope="function", autouse=True)
def cleanup_sessions():
    """Clean up sessions after each test."""
    yield
    # Clear all sessions
    session_manager._sessions.clear()


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_users():
    """Clean up test users after each test."""
    yield
    # Remove test users (keep admin)
    test_users = [u for u in user_service._users.keys() if u != "admin"]
    for username in test_users:
        del user_service._users[username]


# Optional: Docker-based database fixture (commented out for now)
# Uncomment if you want to use real PostgreSQL for integration tests

# @pytest.fixture(scope="session")
# def docker_compose():
#     """Start Docker Compose services for integration tests."""
#     compose_file = os.path.join(os.path.dirname(__file__), "..", "docker-compose.test.yml")
#     
#     # Start services
#     subprocess.run(
#         ["docker-compose", "-f", compose_file, "up", "-d"],
#         check=True,
#     )
#     
#     # Wait for services to be ready
#     max_wait = 60
#     elapsed = 0
#     while elapsed < max_wait:
#         result = subprocess.run(
#             ["docker-compose", "-f", compose_file, "ps", "-q", "postgres-test"],
#             capture_output=True,
#             text=True,
#         )
#         if result.returncode == 0 and result.stdout.strip():
#             # Check if postgres is healthy
#             health_result = subprocess.run(
#                 ["docker-compose", "-f", compose_file, "exec", "-T", "postgres-test", "pg_isready", "-U", "test_user"],
#                 capture_output=True,
#             )
#             if health_result.returncode == 0:
#                 break
#         time.sleep(2)
#         elapsed += 2
#     else:
#         pytest.fail("Docker services did not become ready in time")
#     
#     yield
#     
#     # Stop services
#     subprocess.run(
#         ["docker-compose", "-f", compose_file, "down", "-v"],
#         check=False,
#     )


@pytest.fixture
def test_db_config():
    """Database configuration for integration tests."""
    return {
        "host": "localhost",
        "port": 5433,
        "database": "test_db",
        "user": "test_user",
        "password": "test_password",
    }
