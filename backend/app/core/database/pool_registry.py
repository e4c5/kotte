"""Shared connection pool registry (Milestone D3).

One ``DatabaseConnection`` pool per ``(host, db, user)`` tuple instead of one
per session.  Sessions now hold the pool key; the registry owns the pools.

Caution: pool sharing means one user's query can block another's on the same
``(host, db, user)`` key.  Acceptable for single-tenant or same-user
multi-database use.  For strict resource isolation keep per-session pools and
skip D3 (set a flag to disable the registry).

Usage
-----
    from app.core.database.pool_registry import pool_registry

    db_conn = await pool_registry.get_or_create(
        host, port, database, user, password, sslmode=None
    )
    # db_conn is a connected DatabaseConnection; reuse it across sessions.

Cleanup
-------
    await pool_registry.cleanup_idle(max_idle_seconds=1800)
    await pool_registry.close_all()  # called from lifespan shutdown
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

PoolKey = tuple[str, int, str, str]  # (host, port, database, user)


class PoolRegistry:
    """Process-wide singleton that owns shared ``DatabaseConnection`` pools."""

    def __init__(self):
        self._pools: dict[PoolKey, DatabaseConnection] = {}
        self._last_used: dict[PoolKey, datetime] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, host: str, port: int, database: str, user: str) -> PoolKey:
        return (host, port, database, user)

    async def get_or_create(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        sslmode: Optional[str] = None,
    ) -> DatabaseConnection:
        """Return the shared pool for this tuple, creating it if needed."""
        key = self._make_key(host, port, database, user)
        now = datetime.now(timezone.utc)

        # Fast path: pool already exists and is connected.
        existing = self._pools.get(key)
        if existing is not None and existing._pool is not None and not existing._pool.closed:
            self._last_used[key] = now
            return existing

        async with self._lock:
            # Re-check after acquiring the lock.
            existing = self._pools.get(key)
            if existing is not None and existing._pool is not None and not existing._pool.closed:
                self._last_used[key] = now
                return existing

            logger.info("PoolRegistry: creating pool for %s@%s:%s/%s", user, host, port, database)
            conn = DatabaseConnection(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                sslmode=sslmode,
            )
            await conn.connect()
            self._pools[key] = conn
            self._last_used[key] = now
            return conn

    async def cleanup_idle(self, max_idle_seconds: int = 1800) -> None:
        """Close and evict pools that have been idle for ``max_idle_seconds``."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            idle_keys = [
                k
                for k, last in self._last_used.items()
                if (now - last).total_seconds() > max_idle_seconds
            ]
            for key in idle_keys:
                pool = self._pools.pop(key, None)
                self._last_used.pop(key, None)
                if pool is not None:
                    try:
                        await pool.disconnect()
                        logger.info(
                            "PoolRegistry: closed idle pool for %s@%s:%s/%s", *reversed(key)
                        )
                    except Exception as exc:
                        logger.warning("PoolRegistry: error closing pool %s: %s", key, exc)

    async def close_all(self) -> None:
        """Close every managed pool. Called from app lifespan shutdown."""
        async with self._lock:
            for key, pool in self._pools.items():
                try:
                    await pool.disconnect()
                except Exception as exc:
                    logger.warning("PoolRegistry: error closing pool %s: %s", key, exc)
            self._pools.clear()
            self._last_used.clear()

    def touch(self, host: str, port: int, database: str, user: str) -> None:
        """Update last-used timestamp without acquiring the async lock."""
        key = self._make_key(host, port, database, user)
        if key in self._pools:
            self._last_used[key] = datetime.now(timezone.utc)


pool_registry = PoolRegistry()
