"""Tests for query tracker service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.query_tracker import QueryTracker
from app.core.errors import APIException, ErrorCode


class TestQueryTracker:
    """Tests for query tracking and cancellation."""

    def test_register_query(self):
        """Test registering a query."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        
        assert request_id in tracker._active_queries
        assert tracker._active_queries[request_id]["db_conn"] == mock_db
        assert tracker._active_queries[request_id]["user_id"] == "test_user"

    def test_unregister_query(self):
        """Test unregistering a query."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        tracker.unregister_query(request_id)
        
        assert request_id not in tracker._active_queries

    @pytest.mark.asyncio
    async def test_set_backend_pid(self):
        """Test setting backend PID for a query."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        
        await tracker.set_backend_pid(request_id, 12345)
        
        assert tracker._active_queries[request_id]["backend_pid"] == 12345

    @pytest.mark.asyncio
    async def test_cancel_query_success(self):
        """Test successful query cancellation."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        mock_db.get_backend_pid = AsyncMock(return_value=12345)
        mock_db.cancel_backend = AsyncMock(return_value=True)
        
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        await tracker.set_backend_pid(request_id, 12345)
        
        # Cancel the query
        result = await tracker.cancel_query(request_id, "test_user")
        
        assert result is True
        mock_db.cancel_backend.assert_called_once_with(12345)
        assert request_id not in tracker._active_queries

    @pytest.mark.asyncio
    async def test_cancel_query_wrong_user(self):
        """Test canceling query owned by another user."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="owner_user",
        )
        
        # Try to cancel as different user
        with pytest.raises(APIException) as exc_info:
            await tracker.cancel_query(request_id, "other_user")
        
        assert exc_info.value.code == ErrorCode.QUERY_CANCELLED
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_query_not_found(self):
        """Test canceling a non-existent query."""
        tracker = QueryTracker()
        result = await tracker.cancel_query("nonexistent-id", "test_user")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_query_no_backend_pid(self):
        """Test canceling a query without backend PID."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        mock_db.get_backend_pid = AsyncMock(return_value=None)  # No PID available
        
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        
        # Try to cancel - should fail because no PID
        result = await tracker.cancel_query(request_id, "test_user")
        
        assert result is False

    def test_get_query_info(self):
        """Test getting query information."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        
        info = tracker.get_query_info(request_id)
        
        assert info is not None
        assert info["user_id"] == "test_user"
        assert info["query_text"] == "SELECT 1"

    def test_get_query_info_not_found(self):
        """Test getting info for non-existent query."""
        tracker = QueryTracker()
        info = tracker.get_query_info("nonexistent-id")
        
        assert info is None

    def test_cleanup_stale_queries(self):
        """Test cleaning up stale queries."""
        tracker = QueryTracker()
        request_id = "test-request-id"
        
        mock_db = MagicMock()
        tracker.register_query(
            request_id=request_id,
            db_conn=mock_db,
            query_text="SELECT 1",
            user_id="test_user",
        )
        
        # Manually set started_at to be old
        from datetime import datetime, timezone, timedelta
        tracker._active_queries[request_id]["started_at"] = datetime.now(timezone.utc) - timedelta(hours=2)
        
        # Cleanup queries older than 1 hour
        tracker.cleanup_stale_queries(max_age_seconds=3600)
        
        assert request_id not in tracker._active_queries

