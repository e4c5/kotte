"""Query tracking service for cancellation support."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

logger = logging.getLogger(__name__)


class QueryTracker:
    """Tracks active queries for cancellation support."""

    def __init__(self):
        # Store active queries: request_id -> query_info
        self._active_queries: Dict[str, Dict] = {}

    def register_query(
        self,
        request_id: str,
        db_conn: DatabaseConnection,
        query_text: str,
        user_id: str,
    ) -> None:
        """
        Register an active query.

        Args:
            request_id: Unique request identifier
            db_conn: Database connection
            query_text: SQL query text
            user_id: User ID executing the query
        """
        self._active_queries[request_id] = {
            "db_conn": db_conn,
            "query_text": query_text,
            "user_id": user_id,
            "started_at": datetime.now(timezone.utc),
            "backend_pid": None,  # Will be set when query starts
        }
        logger.debug(f"Registered query {request_id[:8]}...")

    async def set_backend_pid(self, request_id: str, pid: int) -> None:
        """Set the backend PID for a query."""
        if request_id in self._active_queries:
            self._active_queries[request_id]["backend_pid"] = pid
            logger.debug(f"Set backend PID {pid} for query {request_id[:8]}...")

    async def cancel_query(self, request_id: str, user_id: str) -> bool:
        """
        Cancel a running query.

        Args:
            request_id: Request ID of query to cancel
            user_id: User ID requesting cancellation (must match)

        Returns:
            True if cancellation was successful
        """
        query_info = self._active_queries.get(request_id)
        if not query_info:
            logger.warning(f"Query {request_id[:8]}... not found for cancellation")
            return False

        # Verify user owns the query
        if query_info["user_id"] != user_id:
            raise APIException(
                code=ErrorCode.QUERY_CANCELLED,
                message="Cannot cancel query owned by another user",
                category=ErrorCategory.AUTHORIZATION,
                status_code=status.HTTP_403_FORBIDDEN,
            )

        db_conn = query_info["db_conn"]
        backend_pid = query_info.get("backend_pid")

        if not backend_pid:
            # Try to get PID from database
            backend_pid = await db_conn.get_backend_pid()
            if backend_pid:
                query_info["backend_pid"] = backend_pid

        if not backend_pid:
            logger.warning(
                f"Cannot cancel query {request_id[:8]}...: no backend PID available"
            )
            return False

        # Cancel the backend
        success = await db_conn.cancel_backend(backend_pid)
        if success:
            logger.info(f"Cancelled query {request_id[:8]}... (PID: {backend_pid})")
            self.unregister_query(request_id)
        else:
            logger.warning(
                f"Failed to cancel query {request_id[:8]}... (PID: {backend_pid})"
            )

        return success

    def unregister_query(self, request_id: str) -> None:
        """Unregister a query (called when query completes or is cancelled)."""
        if request_id in self._active_queries:
            del self._active_queries[request_id]
            logger.debug(f"Unregistered query {request_id[:8]}...")

    def get_query_info(self, request_id: str) -> Optional[Dict]:
        """Get information about an active query."""
        return self._active_queries.get(request_id)

    def cleanup_stale_queries(self, max_age_seconds: int = 3600) -> None:
        """Remove queries older than max_age_seconds."""
        now = datetime.now(timezone.utc)
        stale_requests = []
        for request_id, info in self._active_queries.items():
            age = (now - info["started_at"]).total_seconds()
            if age > max_age_seconds:
                stale_requests.append(request_id)

        for request_id in stale_requests:
            logger.warning(f"Removing stale query {request_id[:8]}...")
            self.unregister_query(request_id)


# Global query tracker instance
query_tracker = QueryTracker()


