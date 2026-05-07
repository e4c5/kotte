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
    """In-memory session manager for dev / test / single-instance deployments.

    All methods are declared ``async`` to share the same interface as
    ``RedisSessionManager`` so callers can unconditionally ``await`` them.
    """

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    async def create_session(self, user_id: str, connection_config: Optional[dict] = None) -> str:
        await asyncio.sleep(0)
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
        await asyncio.sleep(0)
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

    async def update_session(self, session_id: str, updates: dict) -> None:
        await asyncio.sleep(0)
        if session_id in self._sessions:
            self._sessions[session_id].update(updates)
            self._sessions[session_id]["last_activity"] = datetime.now(timezone.utc)

    async def delete_session(self, session_id: str) -> None:
        await asyncio.sleep(0)
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

    @staticmethod
    def _reconstruct_db_connection(connection_config: dict, session_id: str) -> Optional[Any]:
        """Try to recover a live pool from pool_registry for the given config."""
        host = connection_config.get("host")
        port = connection_config.get("port")
        database = connection_config.get("database")
        user = connection_config.get("user") or connection_config.get("username")
        if not (host and port and database and user):
            return None
        try:
            from app.core.database.pool_registry import pool_registry

            target = (host, int(port), database, user)
            for key, pool in pool_registry._pools.items():
                if key[:4] == target:
                    _local_session_objects.setdefault(session_id, {})["db_connection"] = pool
                    return pool
        except (ValueError, KeyError) as exc:
            logger.debug("Failed to reconstruct db_connection for %s: %s", session_id, exc)
        return None

    def _deserialise(self, raw: str, session_id: str) -> dict:
        data = json.loads(raw)
        for field in ("created_at", "last_activity"):
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field])
        # Re-attach non-serialisable local objects (Item 2: use _local_session_objects as cache)
        local = _local_session_objects.get(session_id, {})
        data.update(local)
        # Item 2: if db_connection is absent, try to reconstruct from pool_registry
        if "db_connection" not in data:
            cfg = data.get("connection_config") or {}
            conn = self._reconstruct_db_connection(cfg, session_id)
            if conn is not None:
                data["db_connection"] = conn
        return data

    async def create_session(self, user_id: str, connection_config: Optional[dict] = None) -> str:
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
        await self._async_set(session_id, session)
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
            now = datetime.now(timezone.utc)
            # Idle timeout check
            idle_timeout = timedelta(seconds=settings.session_idle_timeout)
            if now - session["last_activity"] > idle_timeout:
                logger.info(f"Session {session_id[:8]}... expired (idle timeout)")
                await self._client.delete(self._key(session_id))
                # Item 15: clear process-local objects on expiry
                _local_session_objects.pop(session_id, None)
                return None
            # Absolute max-age check — prevents indefinite session extension
            max_age = timedelta(seconds=settings.session_max_age)
            if now - session["created_at"] > max_age:
                logger.info(f"Session {session_id[:8]}... expired (max age)")
                await self._client.delete(self._key(session_id))
                # Item 15: clear process-local objects on expiry
                _local_session_objects.pop(session_id, None)
                return None
            # Item 22: Refresh TTL using min(idle_ttl, remaining_absolute_ttl)
            idle_ttl = settings.session_idle_timeout
            remaining_absolute_ttl = max(
                1, int((session["created_at"] + max_age - now).total_seconds())
            )
            refresh_ttl = min(idle_ttl, remaining_absolute_ttl)
            session["last_activity"] = now
            await self._client.set(
                self._key(session_id),
                self._serialise(session),
                ex=refresh_ttl,
            )
            return session
        except Exception as exc:
            logger.warning("RedisSessionManager._async_get failed: %s", exc)
            return None

    async def update_session(self, session_id: str, updates: dict) -> None:
        # Non-serialisable keys go to local dict; serialisable go to Redis
        local_updates = {k: v for k, v in updates.items() if k not in self._SERIALISABLE}
        redis_updates = {k: v for k, v in updates.items() if k in self._SERIALISABLE}
        if local_updates:
            _local_session_objects.setdefault(session_id, {}).update(local_updates)
        if redis_updates:
            await self._async_update(session_id, redis_updates)

    async def _async_update(self, session_id: str, updates: dict) -> None:
        raw = await self._client.get(self._key(session_id))
        if raw is None:
            return
        session = self._deserialise(raw, session_id)
        session.update(updates)
        now = datetime.now(timezone.utc)
        session["last_activity"] = now
        # Item 23: preserve absolute max-age — compute remaining TTL from created_at
        max_age = timedelta(seconds=settings.session_max_age)
        remaining_ttl = max(1, int((session["created_at"] + max_age - now).total_seconds()))
        try:
            await self._client.set(
                self._key(session_id),
                self._serialise(session),
                ex=remaining_ttl,
            )
        except Exception as exc:
            logger.warning("RedisSessionManager._async_update failed: %s", exc)

    async def delete_session(self, session_id: str) -> None:
        _local_session_objects.pop(session_id, None)
        try:
            await self._client.delete(self._key(session_id))
        except Exception as exc:
            logger.warning("RedisSessionManager.delete_session failed: %s", exc)
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
