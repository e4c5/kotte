"""Integration tests for authentication flow."""

import pytest
import httpx


class TestAuthenticationFlow:
    """Integration tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client: httpx.AsyncClient):
        """Test successful login flow."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["username"] == "admin"
        assert data["user_id"] == "admin"
        
        # Check that session cookie is set
        assert "set-cookie" in response.headers or any("kotte_session" in str(c) for c in response.cookies.items())

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, async_client: httpx.AsyncClient):
        """Test login with invalid username."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTH_INVALID_SESSION"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, async_client: httpx.AsyncClient):
        """Test login with invalid password."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_current_user_without_auth(self, async_client: httpx.AsyncClient):
        """Test getting current user without authentication."""
        response = await async_client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTH_REQUIRED"

    @pytest.mark.asyncio
    async def test_get_current_user_with_auth(self, authenticated_client: httpx.AsyncClient):
        """Test getting current user with authentication."""
        response = await authenticated_client.get("/api/v1/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "username" in data

    @pytest.mark.asyncio
    async def test_logout_without_auth(self, async_client: httpx.AsyncClient):
        """Test logout without authentication."""
        response = await async_client.post("/api/v1/auth/logout")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_with_auth(self, authenticated_client: httpx.AsyncClient):
        """Test logout with authentication."""
        response = await authenticated_client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert data["logged_out"] is True
        
        # Verify session is invalidated
        me_response = await authenticated_client.get("/api/v1/auth/me")
        assert me_response.status_code == 401

    @pytest.mark.asyncio
    async def test_csrf_token_without_auth(self, async_client: httpx.AsyncClient):
        """Test getting CSRF token without authentication."""
        response = await async_client.get("/api/v1/auth/csrf-token")
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_csrf_token_with_auth(self, authenticated_client: httpx.AsyncClient):
        """Test getting CSRF token with authentication."""
        response = await authenticated_client.get("/api/v1/auth/csrf-token")
        
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 0

    @pytest.mark.asyncio
    async def test_full_auth_flow(self, async_client: httpx.AsyncClient):
        """Test complete authentication flow."""
        # 1. Login
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login_response.status_code == 200
        
        # 2. Get current user
        me_response = await async_client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        
        # 3. Get CSRF token
        csrf_response = await async_client.get("/api/v1/auth/csrf-token")
        assert csrf_response.status_code == 200
        
        # 4. Logout
        logout_response = await async_client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200
        
        # 5. Verify session is invalidated
        me_response_after = await async_client.get("/api/v1/auth/me")
        assert me_response_after.status_code == 401

