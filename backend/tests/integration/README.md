# Integration Test Infrastructure

## Overview

This directory contains integration tests that test the full application stack including middleware, authentication, and database connections.

## Setup

### Prerequisites

- Python 3.10+
- pytest
- pytest-asyncio
- httpx (for async testing if needed)

### Running Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test file
pytest tests/integration/test_auth_flow.py -v

# Run with coverage
pytest tests/integration/ --cov=app --cov-report=html
```

## Fixtures

### `test_app`
Creates a fresh FastAPI application instance with all middleware configured. Settings are overridden for testing:
- CSRF protection: Disabled
- Rate limiting: Disabled
- Session secret: Test key

### `client`
Test client for making HTTP requests. Uses FastAPI's TestClient which properly handles ASGI middleware.

### `authenticated_client`
Test client with an authenticated session. Automatically:
1. Creates a test user
2. Logs in
3. Returns client with session cookie

### `admin_client`
Test client authenticated as admin user.

### `mock_db_connection`
Mock database connection for testing database-dependent endpoints without requiring a real database.

### `connected_client`
Authenticated async client plus a database handle on the session. When
`USE_REAL_TEST_DB` is unset (default), patches `DatabaseConnection` and
injects a mock into `session_manager`. When `USE_REAL_TEST_DB=true`,
calls `POST /api/v1/session/connect` with `TEST_DB_*` settings (defaults
match `apache/age`: `postgres`/`postgres` on port 5432) and disconnects
via `POST /api/v1/session/disconnect` in the fixture teardown — CI runs
this path in `.github/workflows/backend-ci.yml` (integration job).

## Known Limitations

### Session Middleware in TestClient

FastAPI's `TestClient` uses httpx under the hood, which runs the ASGI app in a synchronous context. Some session middleware operations may not work perfectly in this context.

**Workaround**: For tests that require session functionality:
1. Use the service layer directly (e.g., `session_manager`, `user_service`)
2. Mock the session dependency
3. Use async test client (httpx.AsyncClient) with proper async test setup

### Example: Testing with Service Layer

```python
def test_authentication_logic():
    """Test authentication without HTTP layer."""
    user = user_service.authenticate("admin", "admin")
    assert user is not None
    assert user["username"] == "admin"
```

### Example: Mocking Session Dependency

```python
from unittest.mock import patch

def test_endpoint_with_mocked_session(client):
    """Test endpoint with mocked session."""
    mock_session = {
        "user_id": "test-user",
        "session_id": "test-session-id",
    }
    
    with patch('app.core.auth.get_session', return_value=mock_session):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
```

## Test Structure

### Authentication Flow Tests (`test_auth_flow.py`)
- Login/logout flows
- User info retrieval
- CSRF token handling
- Full authentication lifecycle

### Session Flow Tests (`test_session_flow.py`)
- Database connection/disconnection
- Session status
- Connection persistence

## Future Improvements

1. **Async Test Client**: Set up httpx.AsyncClient for proper async testing
2. **Docker Database**: Enable Docker Compose fixture for real database testing
3. **Session Mocking**: Create better session mocking utilities
4. **Test Data Management**: Add fixtures for test data setup/teardown

## Running against a real Apache AGE instance

Tests marked `@pytest.mark.integration` that use `USE_REAL_TEST_DB=true`
need PostgreSQL with the AGE extension (same as production). From repo
root, with AGE listening on `localhost:5432`:

```bash
cd backend && \
  USE_REAL_TEST_DB=true \
  TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=5432 \
  TEST_DB_NAME=postgres TEST_DB_USER=postgres TEST_DB_PASSWORD=postgres \
  pytest -m integration --no-cov -v
```

Use `apache/age:dev_snapshot_PG16` (or another published tag) — see
`deployment/docker-compose.dev.yml` for a full stack. Python **3.11+**
is required for `asyncio.timeout` inside `DatabaseConnection.transaction()`.
