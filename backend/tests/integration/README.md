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
Test client with authenticated session and mocked database connection.

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

## Running with Docker Database

To use a real PostgreSQL database for integration tests:

1. Uncomment the `docker_compose` fixture in `conftest.py`
2. Ensure Docker and docker-compose are installed
3. Run tests with `-m integration` marker

```bash
pytest tests/integration/ -m integration -v
```


