"""Tests for middleware."""

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI

from app.core.middleware import RequestIDMiddleware, CSRFMiddleware, RateLimitMiddleware


class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    @pytest_asyncio.fixture
    async def request_id_client(self):
        """Client backed by app with RequestIDMiddleware enabled."""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            timeout=10.0,
        ) as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_request_id_generated(self, request_id_client: httpx.AsyncClient):
        """Test that request ID is generated and included in response."""
        response = await request_id_client.get("/ping")
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) > 0

    @pytest.mark.asyncio
    async def test_request_id_preserved(self, request_id_client: httpx.AsyncClient):
        """Test that provided request ID is preserved."""
        response = await request_id_client.get(
            "/ping",
            headers={"X-Request-ID": "test-request-id-123"},
        )
        assert response.headers.get("X-Request-ID") == "test-request-id-123"


class TestCSRFMiddleware:
    """Tests for CSRF middleware (disabled in test app)."""

    @pytest.mark.asyncio
    async def test_csrf_token_endpoint_requires_auth(self, async_client: httpx.AsyncClient):
        """CSRF token endpoint requires session (401 without auth)."""
        response = await async_client.get("/api/v1/auth/csrf-token")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_csrf_protection_disabled_in_test(self, async_client: httpx.AsyncClient):
        """Test app has CSRF disabled, so login works without CSRF token."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_works_without_csrf_when_disabled(self, async_client: httpx.AsyncClient):
        """Login works when CSRF is disabled (test app config)."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert response.status_code == 200


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware (disabled in test app)."""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_in_test(self, async_client: httpx.AsyncClient):
        """Test app has rate limit disabled; requests are not throttled."""
        # Multiple requests should all succeed (no 429)
        for _ in range(5):
            response = await async_client.get("/api/v1/auth/me")
            assert response.status_code == 401  # No auth, but not 429
