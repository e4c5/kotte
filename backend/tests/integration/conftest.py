"""Integration test configuration and fixtures."""

import contextlib
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.auth import session_manager

TEST_USER_NAME = "testuser"
TEST_USER_SECRET = "test-user-secret"
ADMIN_USER_NAME = "admin"
ADMIN_USER_SECRET = "admin"

_LOGIN_ENDPOINT = "/api/v1/auth/login"

# Public default for the upstream ``apache/age`` Docker image — not a prod
# secret. Always set ``TEST_DB_PASSWORD`` in CI; operators override locally.
_DEFAULT_INTEGRATION_DB_PASSWORD = "postgres"  # NOSONAR python:S2068


def _integration_db_config() -> dict:
    """Connection params for real-DB paths (``USE_REAL_TEST_DB=true``).

    Defaults match the official ``apache/age`` Docker image (``postgres`` /
    ``postgres`` on port 5432). In GitHub Actions the integration job sets
    ``TEST_DB_HOST=localhost`` because the runner reaches the service via the
    published port (no job-level ``container:``) — see ``.github/workflows/
    backend-ci.yml``.
    """
    return {
        "host": os.getenv("TEST_DB_HOST", "localhost"),
        "port": int(os.getenv("TEST_DB_PORT", "5432")),
        "database": os.getenv("TEST_DB_NAME", "postgres"),
        "user": os.getenv("TEST_DB_USER", "postgres"),
        "password": os.getenv("TEST_DB_PASSWORD", _DEFAULT_INTEGRATION_DB_PASSWORD),
    }


@pytest.fixture(scope="function")
def test_app(monkeypatch):
    """Create a test FastAPI app with all middleware."""
    # Override settings for integration tests BEFORE importing
    monkeypatch.setenv("CSRF_ENABLED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-secret-key-for-integration-tests-only")
    monkeypatch.setenv("ENVIRONMENT", "test")

    # Force reload of config and main modules to pick up new settings
    import sys

    # Remove from cache if present
    modules_to_reload = ["app.core.config", "app.main"]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            del sys.modules[module_name]

    # Import inside the fixture (after the sys.modules eviction above) so the
    # local `create_app` binding references the freshly-loaded module with the
    # test env vars applied. Hoisting this to the module level would freeze it
    # against the import-time settings and silently bypass the CSRF/rate-limit
    # overrides set via monkeypatch.
    from app.main import create_app

    app = create_app()
    # Starlette/AnyIO can deadlock in ASGITransport with stacked BaseHTTPMiddleware.
    # For integration tests, keep behavior-focused middlewares and remove observability-only layers.
    app.user_middleware = [
        m
        for m in app.user_middleware
        if m.cls.__name__ not in {"RequestIDMiddleware", "MetricsMiddleware"}
    ]
    app.middleware_stack = app.build_middleware_stack()
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
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=15.0,
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def authenticated_client(async_client):
    """
    Async test client with authenticated session.

    Creates a user, logs in, and returns client with session cookie.
    """
    # Try to create test user via the API (requires admin session + real DB).
    # Fall back to authenticating as admin when the DB is unavailable (unit
    # test / no-DB environment).
    test_username = TEST_USER_NAME
    test_password = TEST_USER_SECRET

    # Attempt user creation through the API so we never touch service internals.
    admin_login = await async_client.post(
        _LOGIN_ENDPOINT,
        json={"username": ADMIN_USER_NAME, "password": ADMIN_USER_SECRET},
    )
    if admin_login.status_code == 200:
        # Try to create test user; ignore 409 (already exists) and 503 (no DB).
        await async_client.post(
            "/api/v1/users",
            json={"username": test_username, "password": test_password},
        )
        await async_client.post("/api/v1/auth/logout")

    # Login as test user (or fall back to admin credentials when no DB).
    login_response = await async_client.post(
        _LOGIN_ENDPOINT,
        json={"username": test_username, "password": test_password},
    )
    if login_response.status_code != 200:
        login_response = await async_client.post(
            _LOGIN_ENDPOINT,
            json={"username": ADMIN_USER_NAME, "password": ADMIN_USER_SECRET},
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
        _LOGIN_ENDPOINT,
        json={"username": ADMIN_USER_NAME, "password": ADMIN_USER_SECRET},
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
    # Check if we should use real DB or mock
    use_real_db = os.getenv("USE_REAL_TEST_DB", "false").lower() == "true"

    if use_real_db:
        db_config = _integration_db_config()
    else:
        # Use mock for now
        mock_conn = MagicMock()
        mock_conn.is_connected = MagicMock(return_value=True)
        mock_conn.connect = AsyncMock()
        mock_conn.disconnect = AsyncMock()
        mock_conn.execute_query = AsyncMock(return_value=[])
        mock_conn.execute_cypher = AsyncMock(return_value=[])
        mock_conn.execute_scalar = AsyncMock(return_value=None)
        mock_conn.get_backend_pid = AsyncMock(return_value=12345)
        mock_conn.cancel_backend = AsyncMock()

        # Transaction context manager for node delete and other transactional ops
        class _MockTransaction:
            async def __aenter__(self):
                return None

            async def __aexit__(self, *args):
                return None

        mock_conn.transaction = lambda time_limit_seconds=None: _MockTransaction()

        # Patch DatabaseConnection for all modules that use it
        with (
            patch("app.api.v1.session.DatabaseConnection") as mock_db_class,
            patch("app.api.v1.query.DatabaseConnection", mock_db_class),
            patch("app.api.v1.graph.DatabaseConnection", mock_db_class),
            patch("app.api.v1.graph_delete_node.DatabaseConnection", mock_db_class),
        ):
            mock_db_class.return_value = mock_conn

            # Store mock for tests to access
            authenticated_client._mock_db = mock_conn
            authenticated_client._mock_db_class = mock_db_class

            # Avoid calling /session/connect in integration tests: attach mocked DB directly
            # to the authenticated session created by /auth/login.
            session_id = next(iter(session_manager._sessions.keys()), None)
            if not session_id:
                pytest.skip("No active authenticated session found")
            session_manager.update_session(
                session_id,
                {
                    "connection_config": {
                        "host": "localhost",
                        "port": 5432,
                        "database": "test_db",
                        "user": "test_user",
                        "password": "test_password",
                    },
                    "db_connection": mock_conn,
                },
            )

            yield authenticated_client
            return

    # Real DB path — a single pool lives on the session created by
    # ``/session/connect``. Do not pre-connect with a throwaway
    # ``DatabaseConnection`` here: that would open two pools and
    # ``finally`` would only close the unused one.
    try:
        connect_response = await authenticated_client.post(
            "/api/v1/session/connect",
            json={"connection": db_config},
        )

        if connect_response.status_code != 201:
            pytest.skip(f"Failed to connect to database: {connect_response.status_code}")

        yield authenticated_client
    finally:
        disconnect_ok = False
        try:
            resp = await authenticated_client.post("/api/v1/session/disconnect")
            disconnect_ok = resp.status_code == 200
        except Exception:
            pass
        if not disconnect_ok:
            for sess in list(session_manager._sessions.values()):
                db_conn = sess.get("db_connection")
                if db_conn is not None:
                    with contextlib.suppress(Exception):
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
    # User cleanup is handled by the DB (integration tests use a fresh DB per
    # CI run) or is unnecessary (unit tests use only the in-memory admin
    # fallback).  No direct manipulation of UserService internals.
    yield


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
    """Database configuration for integration tests (mirrors ``connected_client``)."""
    return _integration_db_config()
