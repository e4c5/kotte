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
from typing import Any, Optional

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_pool_lock = asyncio.Lock()

_INSERT = """
    INSERT INTO kotte_audit_events (event, actor_id, request_id, payload)
    VALUES (%s, %s, %s, %s)
"""


async def _get_pool() -> Optional[AsyncConnectionPool]:
    global _pool
    if settings.environment == "test":
        return None
    if _pool is not None and not _pool.closed:
        return _pool
    async with _pool_lock:
        if _pool is not None and not _pool.closed:
            return _pool
        try:
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
            await p.open(wait=True, timeout=3)
            _pool = p
        except Exception as exc:
            logger.debug("audit: DB pool unavailable, audit writes will be skipped (%s)", exc)
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
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(
                record(event, actor_id=actor_id, request_id=request_id, payload=payload)
            )
    except RuntimeError:
        pass


async def close() -> None:
    """Gracefully close the audit pool (called from app lifespan)."""
    global _pool
    if _pool is not None and not _pool.closed:
        await _pool.close()
        _pool = None
