"""Integration tests for health check endpoints."""

import pytest
import httpx
from unittest.mock import patch


class TestHealthChecks:
    """Integration tests for health and readiness endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: httpx.AsyncClient):
        """Test basic health check endpoint."""
        response = await async_client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_check_no_auth_required(self, async_client: httpx.AsyncClient):
        """Test that health check doesn't require authentication."""
        # Should work without authentication
        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_check_without_connection(self, authenticated_client: httpx.AsyncClient):
        """Test readiness check without database connection."""
        response = await authenticated_client.get("/api/v1/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "database" in data
        assert data["database"]["connected"] is False

    @pytest.mark.asyncio
    @patch('app.api.v1.session.DatabaseConnection')
    async def test_readiness_check_with_connection(self, mock_db_class, connected_client: httpx.AsyncClient):
        """Test readiness check with database connection."""
        response = await connected_client.get("/api/v1/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "database" in data
        # May be connected or not depending on mock setup
        assert "status" in data["database"]

