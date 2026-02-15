"""Authentication and session management."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, status
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create_session(
        self, user_id: str, connection_config: Optional[dict] = None
    ) -> str:
        """
        Create a new session and return session ID.
        
        Args:
            user_id: User ID
            connection_config: Optional connection config (for DB connections)
        """
        session_id = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)

        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": now,
            "last_activity": now,
            "connection_config": connection_config or {},
            "graph_context": None,
        }

        logger.info(f"Created session {session_id[:8]}... for user {user_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data if valid."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check idle timeout
        idle_timeout = timedelta(seconds=settings.session_idle_timeout)
        if datetime.now(timezone.utc) - session["last_activity"] > idle_timeout:
            logger.info(f"Session {session_id[:8]}... expired (idle timeout)")
            del self._sessions[session_id]
            return None

        # Check max age
        max_age = timedelta(seconds=settings.session_max_age)
        if datetime.now(timezone.utc) - session["created_at"] > max_age:
            logger.info(f"Session {session_id[:8]}... expired (max age)")
            del self._sessions[session_id]
            return None

        # Update last activity
        session["last_activity"] = datetime.now(timezone.utc)
        return session

    def update_session(self, session_id: str, updates: dict) -> None:
        """Update session data."""
        if session_id in self._sessions:
            self._sessions[session_id].update(updates)
            self._sessions[session_id]["last_activity"] = datetime.now(
                timezone.utc
            )

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        if session_id in self._sessions:
            logger.info(f"Deleted session {session_id[:8]}...")
            del self._sessions[session_id]

    def get_user_id(self, session_id: str) -> Optional[str]:
        """Get user ID from session."""
        session = self.get_session(session_id)
        return session["user_id"] if session else None


session_manager = SessionManager()


def get_session(request: Request) -> dict:
    """Get current session from request."""
    session_id = request.session.get("session_id")
    if not session_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session = session_manager.get_session(session_id)
    if not session:
        raise APIException(
            code=ErrorCode.AUTH_SESSION_EXPIRED,
            message="Session expired or invalid",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return session


def require_auth(request: Request) -> dict:
    """Middleware function to require authentication."""
    return get_session(request)

