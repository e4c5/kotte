"""Tests for middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import RequestIDMiddleware, CSRFMiddleware, RateLimitMiddleware


class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    def test_request_id_generated(self, client: TestClient):
        """Test that request ID is generated and included in response."""
        response = client.get("/api/v1/auth/me")
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0

    def test_request_id_preserved(self, client: TestClient):
        """Test that provided request ID is preserved."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"X-Request-ID": "test-request-id-123"},
        )
        assert response.headers.get("X-Request-ID") == "test-request-id-123"


class TestCSRFMiddleware:
    """Tests for CSRF middleware (disabled in test app)."""

    def test_csrf_token_endpoint_requires_auth(self, client: TestClient):
        """CSRF token endpoint requires session (401 without auth)."""
        response = client.get("/api/v1/auth/csrf-token")
        assert response.status_code == 401

    def test_csrf_protection_disabled_in_test(self, client: TestClient):
        """Test app has CSRF disabled, so login works without CSRF token."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200

    def test_login_works_without_csrf_when_disabled(self, client: TestClient):
        """Login works when CSRF is disabled (test app config)."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware (disabled in test app)."""

    def test_rate_limit_disabled_in_test(self, client: TestClient):
        """Test app has rate limit disabled; requests are not throttled."""
        # Multiple requests should all succeed (no 429)
        for _ in range(5):
            response = client.get("/api/v1/auth/me")
            assert response.status_code == 401  # No auth, but not 429

