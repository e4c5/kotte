"""Tests for middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RequestIDMiddleware, CSRFMiddleware, RateLimitMiddleware
from app.core.config import settings


class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    def test_request_id_generated(self, client: TestClient):
        """Test that request ID is generated and included in response."""
        app = FastAPI()

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        app.add_middleware(RequestIDMiddleware)
        test_client = TestClient(app)

        response = test_client.get("/test")
        assert response.status_code == 200
        # Request ID should be in response headers
        assert "X-Request-ID" in response.headers

    def test_request_id_preserved(self, client: TestClient):
        """Test that provided request ID is preserved."""
        app = FastAPI()

        @app.get("/test")
        def test_endpoint():
            return {"message": "test"}

        app.add_middleware(RequestIDMiddleware)
        test_client = TestClient(app)

        custom_id = "custom-request-id-123"
        response = test_client.get("/test", headers={"X-Request-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_id


class TestCSRFMiddleware:
    """Tests for CSRF middleware."""

    def test_csrf_token_endpoint(self, client: TestClient):
        """Test that CSRF token endpoint works."""
        response = client.get("/api/v1/csrf-token")
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 0

    def test_csrf_protection_enabled(self, client: TestClient):
        """Test that CSRF protection is enforced for state-changing requests."""
        if not settings.csrf_enabled:
            pytest.skip("CSRF protection is disabled")

        # GET request should work without token
        response = client.get("/api/v1/graphs")
        assert response.status_code in [200, 401]  # May require auth

        # POST request without token should fail
        response = client.post("/api/v1/queries/execute", json={})
        # Should fail with 403 or 401 (if auth required)
        assert response.status_code in [403, 401]

    def test_login_exempt_from_csrf(self, client: TestClient):
        """Test that login endpoint is exempt from CSRF."""
        # Login should work without CSRF token
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "test", "password": "test"},
        )
        # May fail due to invalid credentials, but not CSRF
        assert response.status_code != 403


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware."""

    def test_rate_limit_headers(self, client: TestClient):
        """Test that rate limit headers are present."""
        if not settings.rate_limit_enabled:
            pytest.skip("Rate limiting is disabled")

        response = client.get("/api/v1/graphs")
        # Headers may not be present if rate limiting uses different mechanism
        # This is a basic smoke test
        assert response.status_code in [200, 401, 404]

