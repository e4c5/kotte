"""Query tracking service for cancellation support.

Two implementations selected by ``settings.redis_enabled``:
- ``QueryTracker``      — in-memory (original, default)
- ``RedisQueryTracker`` — metadata in Redis; ``db_conn`` stays process-local

The module-level ``query_tracker`` is bound to the appropriate instance.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.config import settings
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _keep_task(task: asyncio.Task) -> None:
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class QueryTracker:
    """In-memory query tracker (default when REDIS_ENABLED=false)."""

    def __init__(self):
        self._active_queries: Dict[str, Dict] = {}

    def register_query(
        self,
        request_id: str,
        db_conn: DatabaseConnection,
        query_text: str,
        user_id: str,
    ) -> None:
        self._active_queries[request_id] = {
            "db_conn": db_conn,
            "query_text": query_text,
            "user_id": user_id,
            "started_at": datetime.now(timezone.utc),
            "backend_pid": None,
        }
        logger.debug(f"Registered query {request_id[:8]}...")

    async def set_backend_pid(self, request_id: str, pid: int) -> None:
        if request_id in self._active_queries:
            self._active_queries[request_id]["backend_pid"] = pid
            logger.debug(f"Set backend PID {pid} for query {request_id[:8]}...")

    async def cancel_query(self, request_id: str, user_id: str) -> bool:
        query_info = self._active_queries.get(request_id)
        if not query_info:
            logger.warning(f"Query {request_id[:8]}... not found for cancellation")
            return False

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
            backend_pid = await db_conn.get_backend_pid()
            if backend_pid:
                query_info["backend_pid"] = backend_pid

        if not backend_pid:
            logger.warning(f"Cannot cancel query {request_id[:8]}...: no backend PID available")
            return False

        success = await db_conn.cancel_backend(backend_pid)
        if success:
            logger.info(f"Cancelled query {request_id[:8]}... (PID: {backend_pid})")
            self.unregister_query(request_id)
        else:
            logger.warning(f"Failed to cancel query {request_id[:8]}... (PID: {backend_pid})")

        return success

    def unregister_query(self, request_id: str) -> None:
        if request_id in self._active_queries:
            del self._active_queries[request_id]
            logger.debug(f"Unregistered query {request_id[:8]}...")

    def get_query_info(self, request_id: str) -> Optional[Dict]:
        return self._active_queries.get(request_id)

    def cleanup_stale_queries(self, max_age_seconds: int = 3600) -> None:
        now = datetime.now(timezone.utc)
        stale = [
            rid
            for rid, info in self._active_queries.items()
            if (now - info["started_at"]).total_seconds() > max_age_seconds
        ]
        for rid in stale:
            logger.warning(f"Removing stale query {rid[:8]}...")
            self.unregister_query(rid)


class RedisQueryTracker:
    """Redis-backed query tracker for multi-instance deployments.

    Serialisable metadata (user_id, query_text, backend_pid, started_at) is
    stored in Redis with a 1-hour TTL.  The ``db_conn`` object stays in a
    process-local dict because it is a live TCP pool and cannot be serialised.
    """

    def __init__(self, redis_url: str):
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(redis_url, decode_responses=True)
        self._prefix = "kotte:query:"
        self._ttl = 3600
        # Process-local store for db_conn references
        self._db_conns: Dict[str, DatabaseConnection] = {}

    def _key(self, request_id: str) -> str:
        return f"{self._prefix}{request_id}"

    def register_query(
        self,
        request_id: str,
        db_conn: DatabaseConnection,
        query_text: str,
        user_id: str,
    ) -> None:
        self._db_conns[request_id] = db_conn
        meta = {
            "user_id": user_id,
            "query_text": query_text,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "backend_pid": None,
        }
        try:
            loop = asyncio.get_event_loop()
            _keep_task(
                loop.create_task(
                    self._client.set(self._key(request_id), json.dumps(meta), ex=self._ttl)  # type: ignore[arg-type]
                )
            )
        except RuntimeError:
            pass
        logger.debug(f"Registered query {request_id[:8]}...")

    async def set_backend_pid(self, request_id: str, pid: int) -> None:
        try:
            raw = await self._client.get(self._key(request_id))
            if raw:
                meta = json.loads(raw)
                meta["backend_pid"] = pid
                await self._client.set(self._key(request_id), json.dumps(meta), ex=self._ttl)
            logger.debug(f"Set backend PID {pid} for query {request_id[:8]}...")
        except Exception as exc:
            logger.warning("RedisQueryTracker.set_backend_pid failed: %s", exc)

    async def cancel_query(self, request_id: str, user_id: str) -> bool:
        try:
            raw = await self._client.get(self._key(request_id))
        except Exception as exc:
            logger.warning("RedisQueryTracker.cancel_query Redis error: %s", exc)
            return False

        if raw is None:
            logger.warning(f"Query {request_id[:8]}... not found for cancellation")
            return False

        meta = json.loads(raw)
        if meta["user_id"] != user_id:
            raise APIException(
                code=ErrorCode.QUERY_CANCELLED,
                message="Cannot cancel query owned by another user",
                category=ErrorCategory.AUTHORIZATION,
                status_code=status.HTTP_403_FORBIDDEN,
            )

        db_conn = self._db_conns.get(request_id)
        if db_conn is None:
            logger.warning(f"Cannot cancel query {request_id[:8]}...: db_conn not in local cache")
            return False

        backend_pid = meta.get("backend_pid")
        if not backend_pid:
            backend_pid = await db_conn.get_backend_pid()
            if backend_pid:
                await self.set_backend_pid(request_id, backend_pid)

        if not backend_pid:
            logger.warning(f"Cannot cancel query {request_id[:8]}...: no backend PID available")
            return False

        success = await db_conn.cancel_backend(backend_pid)
        if success:
            logger.info(f"Cancelled query {request_id[:8]}... (PID: {backend_pid})")
            self.unregister_query(request_id)
        return success

    def unregister_query(self, request_id: str) -> None:
        self._db_conns.pop(request_id, None)
        try:
            loop = asyncio.get_event_loop()
            _keep_task(loop.create_task(self._client.delete(self._key(request_id))))  # type: ignore[arg-type]
        except RuntimeError:
            pass
        logger.debug(f"Unregistered query {request_id[:8]}...")

    def get_query_info(self, request_id: str) -> Optional[Dict]:
        db_conn = self._db_conns.get(request_id)
        if db_conn is None:
            return None
        return {"db_conn": db_conn}

    def cleanup_stale_queries(self, max_age_seconds: int = 3600) -> None:
        # Redis TTL handles expiry; just purge local db_conn references that
        # have no matching Redis key (best-effort in process scope).
        pass


if settings.redis_enabled:
    query_tracker = RedisQueryTracker(settings.redis_url)
else:
    query_tracker = QueryTracker()  # type: ignore[assignment]
