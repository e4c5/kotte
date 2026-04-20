"""Simple in-memory caching service with TTL and size limits."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class InMemoryCache:
    """
    A simple thread-safe in-memory cache with TTL support.

    This is intended for metadata and session-level caching to reduce
    expensive database operations.
    """

    def __init__(self, name: str, default_ttl_seconds: int = 3600, max_size: int = 1000):
        self.name = name
        self._cache: Dict[str, Tuple[Any, datetime, timedelta]] = {}
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it hasn't expired."""
        async with self._lock:
            if key not in self._cache:
                metrics.record_cache_request(self.name, "miss")
                return None

            value, timestamp, ttl = self._cache[key]
            if datetime.now(timezone.utc) - timestamp < ttl:
                metrics.record_cache_request(self.name, "hit")
                return value

            # Expired
            metrics.record_cache_request(self.name, "miss")
            del self._cache[key]
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a value in the cache with an optional TTL."""
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else self._default_ttl

        async with self._lock:
            # Simple eviction policy
            if len(self._cache) >= self._max_size:
                self._cleanup_expired()
                if len(self._cache) >= self._max_size:
                    # Still too large, clear oldest 10%
                    keys_to_remove = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])[
                        : max(1, self._max_size // 10)
                    ]
                    for k in keys_to_remove:
                        del self._cache[k]

            self._cache[key] = (value, datetime.now(timezone.utc), ttl)

    async def delete(self, key: str) -> None:
        """Remove a specific key from the cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self, prefix: Optional[str] = None) -> None:
        """Clear all keys, optionally filtered by prefix."""
        async with self._lock:
            if prefix:
                keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
                for k in keys_to_remove:
                    del self._cache[k]
            else:
                self._cache.clear()

    def get_sync(self, key: str) -> Optional[Any]:
        """Synchronous version of get for tests (no lock)."""
        if key not in self._cache:
            return None
        value, timestamp, ttl = self._cache[key]
        if datetime.now(timezone.utc) - timestamp < ttl:
            return value
        return None

    def set_sync(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Synchronous version of set for tests (no lock)."""
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds is not None else self._default_ttl
        self._cache[key] = (value, datetime.now(timezone.utc), ttl)

    def _cleanup_expired(self) -> None:
        """Remove all expired items. Not thread-safe, call from locked method."""
        now = datetime.now(timezone.utc)
        expired_keys = [k for k, (v, ts, ttl) in self._cache.items() if now - ts >= ttl]
        for k in expired_keys:
            del self._cache[k]


# Global cache instances for different purposes
metadata_cache = InMemoryCache(name="metadata", default_ttl_seconds=3600, max_size=2000)
session_cache = InMemoryCache(name="session", default_ttl_seconds=1800, max_size=1000)
