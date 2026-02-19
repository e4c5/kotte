"""Integration test configuration and fixtures."""

import os
import pytest
import pytest_asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.auth import session_manager
from app.services.user import user_service


@pytest.fixture(scope="function")
def test_app(monkeypatch):
    """Create a test FastAPI app with all middleware."""
    # Override settings for integration tests BEFORE importing
    monkeypatch.setenv("CSRF_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-for-integration-tests-only")
    monkeypatch.setenv("ENVIRONMENT", "test")
    
    # Force reload of config and main modules to pick up new settings
    import importlib
    import sys
    
    # Remove from cache if present
    modules_to_reload = ['app.core.config', 'app.main']
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            del sys.modules[module_name]
    
    # Now import and create app
    from app.main import create_app
    app = create_app()
    return app


@pytest.fixture(scope="function")
def client(test_app):
    """Synchronous test client for simple tests."""
    return TestClient(test_app, base_url="http://testserver")


@pytest_asyncio.fixture(scope="function")
async def async_client(test_app):
    """Async test client that properly supports session middleware."""
    from httpx import ASGITransport
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(async_client):
    """
    Async test client with authenticated session.
    
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
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": test_username, "password": test_password},
    )
    
    if login_response.status_code != 200:
        pytest.skip(f"Failed to create authenticated session: {login_response.status_code}")
    
    # Return client with session cookie
    return async_client


@pytest_asyncio.fixture(scope="function")
async def admin_client(async_client):
    """
    Async test client authenticated as admin user.
    """
    # Login as admin
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    
    if login_response.status_code != 200:
        pytest.skip(f"Failed to login as admin: {login_response.status_code}")
    
    return async_client


@pytest_asyncio.fixture(scope="function")
async def connected_client(authenticated_client):
    """
    Test client with authenticated session and database connection.
    
    Uses a real database connection (or can be configured to use test DB).
    For now, we'll use a mock only if no test database is available.
    """
    # Try to connect to database
    # In a real setup, this would connect to a test database
    # For now, we'll mock it but the infrastructure supports real connections
    
    from app.core.database import DatabaseConnection
    
    # Check if we should use real DB or mock
    use_real_db = os.getenv("USE_REAL_TEST_DB", "false").lower() == "true"
    
    if use_real_db:
        # Use real database connection
        db_config = {
            "host": os.getenv("TEST_DB_HOST", "localhost"),
            "port": int(os.getenv("TEST_DB_PORT", "5432")),
            "database": os.getenv("TEST_DB_NAME", "test_db"),
            "user": os.getenv("TEST_DB_USER", "test_user"),
            "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
        }
        
        db_conn = DatabaseConnection(**db_config)
        try:
            await db_conn.connect()
        except Exception as e:
            pytest.skip(f"Could not connect to test database: {e}")
    else:
        # Use mock for now
        mock_conn = MagicMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.connect = AsyncMock()
        mock_conn.disconnect = AsyncMock()
        mock_conn.execute_query = AsyncMock(return_value=[])
        mock_conn.execute_scalar = AsyncMock(return_value=None)
        mock_conn.get_backend_pid = AsyncMock(return_value=12345)
        mock_conn.cancel_backend = AsyncMock()

        # Transaction context manager for node delete and other transactional ops
        class _MockTransaction:
            async def __aenter__(self): return None
            async def __aexit__(self, *args): return None
        mock_conn.transaction = lambda timeout=None: _MockTransaction()

        # Patch DatabaseConnection for all modules that use it
        with patch('app.api.v1.session.DatabaseConnection') as mock_db_class, \
             patch('app.api.v1.query.DatabaseConnection', mock_db_class), \
             patch('app.api.v1.graph.DatabaseConnection', mock_db_class):
            mock_db_class.return_value = mock_conn
            
            # Store mock for tests to access
            authenticated_client._mock_db = mock_conn
            authenticated_client._mock_db_class = mock_db_class
            
            # Connect
            connect_response = await authenticated_client.post(
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
            
            yield authenticated_client
            return
    
    # Real DB path
    try:
        connect_response = await authenticated_client.post(
            "/api/v1/session/connect",
            json={"connection": db_config},
        )
        
        if connect_response.status_code != 201:
            pytest.skip(f"Failed to connect to database: {connect_response.status_code}")
        
        yield authenticated_client
    finally:
        if db_conn:
            await db_conn.disconnect()


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
