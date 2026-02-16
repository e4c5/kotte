"""Integration tests for authentication flow."""

import pytest
from fastapi.testclient import TestClient


class TestAuthenticationFlow:
    """Integration tests for authentication endpoints."""

    def test_login_success(self, client: TestClient):
        """Test successful login flow."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["username"] == "admin"
        assert data["user_id"] == "admin"
        
        # Check that session cookie is set
        assert "Set-Cookie" in response.headers
        cookies = response.headers["Set-Cookie"]
        assert "kotte_session" in cookies or "session" in cookies.lower()

    def test_login_invalid_username(self, client: TestClient):
        """Test login with invalid username."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nonexistent", "password": "password"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTH_INVALID_SESSION"

    def test_login_invalid_password(self, client: TestClient):
        """Test login with invalid password."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    def test_get_current_user_without_auth(self, client: TestClient):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTH_REQUIRED"

    def test_get_current_user_with_auth(self, authenticated_client: TestClient):
        """Test getting current user with authentication."""
        response = authenticated_client.get("/api/v1/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "username" in data

    def test_logout_without_auth(self, client: TestClient):
        """Test logout without authentication."""
        response = client.post("/api/v1/auth/logout")
        
        assert response.status_code == 401

    def test_logout_with_auth(self, authenticated_client: TestClient):
        """Test logout with authentication."""
        response = authenticated_client.post("/api/v1/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert data["logged_out"] is True
        
        # Verify session is invalidated
        me_response = authenticated_client.get("/api/v1/auth/me")
        assert me_response.status_code == 401

    def test_csrf_token_without_auth(self, client: TestClient):
        """Test getting CSRF token without authentication."""
        response = client.get("/api/v1/auth/csrf-token")
        
        assert response.status_code == 401

    def test_csrf_token_with_auth(self, authenticated_client: TestClient):
        """Test getting CSRF token with authentication."""
        response = authenticated_client.get("/api/v1/auth/csrf-token")
        
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 0

    def test_full_auth_flow(self, client: TestClient):
        """Test complete authentication flow."""
        # 1. Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login_response.status_code == 200
        
        # 2. Get current user
        me_response = client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        
        # 3. Get CSRF token
        csrf_response = client.get("/api/v1/auth/csrf-token")
        assert csrf_response.status_code == 200
        
        # 4. Logout
        logout_response = client.post("/api/v1/auth/logout")
        assert logout_response.status_code == 200
        
        # 5. Verify session is invalidated
        me_response_after = client.get("/api/v1/auth/me")
        assert me_response_after.status_code == 401

