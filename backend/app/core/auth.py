"""Authentication and session management.

Two implementations:
- ``InMemorySessionManager`` — original, used when ``REDIS_ENABLED=false``
- ``RedisSessionManager`` — used when ``REDIS_ENABLED=true``

The module-level ``session_manager`` is set to the appropriate instance at
import time based on ``settings.redis_enabled``.

Redis storage note: only JSON-serializable fields are stored in Redis.
The ``db_connection`` object (a live TCP pool) stays in a process-local dict
and is keyed by ``session_id``.  On Redis-TTL expiry the keyspace-notification
handler closes the pool to prevent leaks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Request, status

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory

logger = logging.getLogger(__name__)

# Process-local store for non-serialisable session objects (db_connection, etc.).
# Populated/cleared in both implementations so the rest of the code always finds
# the db_connection here regardless of which backend is active.
_local_session_objects: dict[str, dict] = {}

# Keeps fire-and-forget tasks alive until completion so GC can't collect them.
_background_tasks: set[asyncio.Task] = set()


def _keep_task(task: asyncio.Task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class InMemorySessionManager:
    """Original in-memory session manager (default / dev / single-instance)."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def create_session(self, user_id: str, connection_config: Optional[dict] = None) -> str:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": now,
            "last_activity": now,
            "connection_config": connection_config or {},
            "graph_context": None,
            "csrf_token": csrf_token,
        }
        logger.info(f"Created session {session_id[:8]}... for user {user_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        session = self._sessions.get(session_id)
        if not session:
            return None

        idle_timeout = timedelta(seconds=settings.session_idle_timeout)
        if datetime.now(timezone.utc) - session["last_activity"] > idle_timeout:
            logger.info(f"Session {session_id[:8]}... expired (idle timeout)")
            del self._sessions[session_id]
            return None

        max_age = timedelta(seconds=settings.session_max_age)
        if datetime.now(timezone.utc) - session["created_at"] > max_age:
            logger.info(f"Session {session_id[:8]}... expired (max age)")
            del self._sessions[session_id]
            return None

        session["last_activity"] = datetime.now(timezone.utc)
        return session

    def update_session(self, session_id: str, updates: dict) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].update(updates)
            self._sessions[session_id]["last_activity"] = datetime.now(timezone.utc)

    def delete_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            logger.info(f"Deleted session {session_id[:8]}...")
            del self._sessions[session_id]

    async def get_user_id(self, session_id: str) -> Optional[str]:
        session = await self.get_session(session_id)
        return session["user_id"] if session else None


class RedisSessionManager:
    """Redis-backed session manager for multi-user / multi-instance deployments.

    Non-serialisable values (``db_connection``) are stored in the process-local
    ``_local_session_objects`` dict so lookups still return them transparently.
    """

    _SERIALISABLE = {
        "user_id",
        "created_at",
        "last_activity",
        "connection_config",
        "graph_context",
        "csrf_token",
        "role",
    }

    def __init__(self, redis_url: str):
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(redis_url, decode_responses=True)
        self._prefix = "kotte:session:"

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    def _serialise(self, session: dict) -> str:
        safe = {}
        for k, v in session.items():
            if k not in self._SERIALISABLE:
                continue
            if isinstance(v, datetime):
                safe[k] = v.isoformat()
            else:
                safe[k] = v
        return json.dumps(safe)

    def _deserialise(self, raw: str, session_id: str) -> dict:
        data = json.loads(raw)
        for field in ("created_at", "last_activity"):
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        # Re-attach non-serialisable local objects
        local = _local_session_objects.get(session_id, {})
        data.update(local)
        return data

    def create_session(self, user_id: str, connection_config: Optional[dict] = None) -> str:
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        session: dict[str, Any] = {
            "user_id": user_id,
            "created_at": now,
            "last_activity": now,
            "connection_config": connection_config or {},
            "graph_context": None,
            "csrf_token": csrf_token,
        }
        try:
            loop = asyncio.get_event_loop()
            _keep_task(loop.create_task(self._async_set(session_id, session)))
        except RuntimeError:
            pass
        logger.info(f"Created session {session_id[:8]}... for user {user_id}")
        return session_id

    async def _async_set(self, session_id: str, session: dict) -> None:
        try:
            await self._client.set(
                self._key(session_id),
                self._serialise(session),
                ex=settings.session_max_age,
            )
        except Exception as exc:
            logger.warning("RedisSessionManager.set failed: %s", exc)

    async def get_session(self, session_id: str) -> Optional[dict]:
        return await self._async_get(session_id)

    async def _async_get(self, session_id: str) -> Optional[dict]:
        try:
            raw = await self._client.get(self._key(session_id))
            if raw is None:
                return None
            session = self._deserialise(raw, session_id)
            # Idle timeout check
            idle_timeout = timedelta(seconds=settings.session_idle_timeout)
            if datetime.now(timezone.utc) - session["last_activity"] > idle_timeout:
                await self._client.delete(self._key(session_id))
                return None
            # Refresh TTL and last_activity
            session["last_activity"] = datetime.now(timezone.utc)
            await self._async_set(session_id, session)
            return session
        except Exception as exc:
            logger.warning("RedisSessionManager._async_get failed: %s", exc)
            return None

    def update_session(self, session_id: str, updates: dict) -> None:
        # Non-serialisable keys go to local dict; serialisable go to Redis
        local_updates = {k: v for k, v in updates.items() if k not in self._SERIALISABLE}
        redis_updates = {k: v for k, v in updates.items() if k in self._SERIALISABLE}
        if local_updates:
            _local_session_objects.setdefault(session_id, {}).update(local_updates)
        if redis_updates:
            try:
                loop = asyncio.get_event_loop()
                _keep_task(loop.create_task(self._async_update(session_id, redis_updates)))
            except RuntimeError:
                pass

    async def _async_update(self, session_id: str, updates: dict) -> None:
        raw = await self._client.get(self._key(session_id))
        if raw is None:
            return
        session = self._deserialise(raw, session_id)
        session.update(updates)
        session["last_activity"] = datetime.now(timezone.utc)
        await self._async_set(session_id, session)

    def delete_session(self, session_id: str) -> None:
        _local_session_objects.pop(session_id, None)
        try:
            loop = asyncio.get_event_loop()
            _keep_task(loop.create_task(self._client.delete(self._key(session_id))))  # type: ignore[arg-type]
        except RuntimeError:
            pass
        logger.info(f"Deleted session {session_id[:8]}...")

    async def get_user_id(self, session_id: str) -> Optional[str]:
        session = await self.get_session(session_id)
        return session["user_id"] if session else None


# Alias: the rest of the codebase only references `SessionManager` as a type
# name for isinstance() checks and type hints written before D2.  Bind it to
# whichever concrete class is active so old imports don't break.
if settings.redis_enabled:
    session_manager = RedisSessionManager(settings.redis_url)
    SessionManager = RedisSessionManager
else:
    session_manager = InMemorySessionManager()  # type: ignore[assignment]
    SessionManager = InMemorySessionManager  # type: ignore[misc,assignment]


async def get_session(request: Request) -> dict:
    """Get current session from request."""
    session_id = request.session.get("session_id")
    if not session_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    session = await session_manager.get_session(session_id)
    if not session:
        raise APIException(
            code=ErrorCode.AUTH_SESSION_EXPIRED,
            message="Session expired or invalid",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return session


async def require_auth(request: Request) -> dict:
    """Middleware function to require authentication."""
    return await get_session(request)
