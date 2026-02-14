"""Tests for error handling."""

from fastapi.testclient import TestClient

from app.core.errors import APIException, ErrorCode, ErrorCategory


def test_error_response_structure(client: TestClient):
    """Test that error responses follow the required structure."""
    # Make a request to a non-existent endpoint
    response = client.get("/api/v1/nonexistent")
    
    assert response.status_code == 404
    data = response.json()
    
    # Check error structure
    assert "error" in data
    error = data["error"]
    assert "code" in error
    assert "category" in error
    assert "message" in error
    assert "request_id" in error
    assert "timestamp" in error
    assert "retryable" in error


def test_api_exception():
    """Test APIException creation."""
    exc = APIException(
        code=ErrorCode.AUTH_REQUIRED,
        message="Test error",
        category=ErrorCategory.AUTHENTICATION,
        status_code=401,
    )
    
    assert exc.code == ErrorCode.AUTH_REQUIRED
    assert exc.message == "Test error"
    assert exc.category == ErrorCategory.AUTHENTICATION
    assert exc.status_code == 401

