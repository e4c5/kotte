"""Audit logging service.

Writes to ``kotte_audit_events`` (created by Alembic revision a1b2c3d4e5f6).
Uses the *application* database (settings.db_*), not any user-supplied DB.

Public API
----------
``record(event, *, actor_id, request_id, payload)``
    Fire-and-forget coroutine; errors are caught and logged so an audit
    failure never breaks the main request path.

``fire_and_forget(event, ...)``
    Synchronous helper that schedules ``record()`` as a background task.
    Use this from middleware where you cannot ``await``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_pool_lock = asyncio.Lock()
_pool_retry_after: Optional[datetime] = None  # time-based circuit breaker
_RETRY_BACKOFF_SECONDS = 60

_INSERT = """
    INSERT INTO kotte_audit_events (event, actor_id, request_id, payload)
    VALUES (%s, %s, %s, %s)
"""


async def _get_pool() -> Optional[AsyncConnectionPool]:
    global _pool, _pool_retry_after
    if settings.environment == "test":
        return None
    if _pool is not None and not _pool.closed:
        return _pool
    now = datetime.now(timezone.utc)
    if _pool_retry_after is not None and now < _pool_retry_after:
        return None
    async with _pool_lock:
        if _pool is not None and not _pool.closed:
            return _pool
        now = datetime.now(timezone.utc)
        if _pool_retry_after is not None and now < _pool_retry_after:
            return None
        conninfo = make_conninfo(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=2,
        )
        p = AsyncConnectionPool(
            conninfo,
            min_size=1,
            max_size=3,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=False,
        )
        try:
            await asyncio.wait_for(p.open(wait=True, timeout=3), timeout=4)
            _pool = p
            _pool_retry_after = None
        except Exception as exc:
            try:
                await p.close()
            except Exception:
                pass
            _pool_retry_after = datetime.now(timezone.utc) + timedelta(
                seconds=_RETRY_BACKOFF_SECONDS
            )
            logger.debug(
                "audit: DB pool unavailable, retrying in %ds (%s)", _RETRY_BACKOFF_SECONDS, exc
            )
    return _pool


async def record(
    event: str,
    *,
    actor_id: Optional[str] = None,
    request_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Insert one audit row. Errors are swallowed so callers never fail."""
    try:
        pool = await _get_pool()
        if pool is None:
            return
        async with pool.connection() as conn:
            await conn.execute(
                _INSERT,
                (
                    event,
                    actor_id,
                    request_id,
                    json.dumps(payload) if payload is not None else None,
                ),
            )
    except Exception:
        logger.warning("audit.record failed (event=%s)", event, exc_info=True)


def fire_and_forget(
    event: str,
    *,
    actor_id: Optional[str] = None,
    request_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Schedule an audit write without blocking the caller."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(record(event, actor_id=actor_id, request_id=request_id, payload=payload))
    except RuntimeError:
        pass


def reset_pool() -> None:
    """Clear the circuit breaker so the next call to _get_pool() retries immediately."""
    global _pool_retry_after
    _pool_retry_after = None


async def close() -> None:
    """Gracefully close the audit pool (called from app lifespan)."""
    global _pool
    if _pool is not None and not _pool.closed:
        await _pool.close()
        _pool = None
