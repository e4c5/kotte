"""User management service (D1 — DB-backed).

Uses the Kotte management database (settings.db_*) and the ``kotte_users``
table created by Alembic revision ``78c03fa27fda``.

Graceful fallback: if the DB is unreachable (e.g. in unit tests without a
live Postgres), the built-in admin account is served from memory so existing
tests and single-developer local runs continue to work without a running DB.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, cast

import bcrypt
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

logger = logging.getLogger(__name__)

_pool: Optional[AsyncConnectionPool] = None
_pool_lock: Optional[asyncio.Lock] = None
_pool_unavailable: bool = False  # Item 9: circuit breaker flag


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _admin_password() -> str:
    pw = os.environ.get("ADMIN_PASSWORD", "admin")
    if pw == "admin" and settings.environment == "production":
        logger.warning("Default admin password in use. Set ADMIN_PASSWORD in production!")
    return pw


_admin_fallback: Optional[dict] = None


def _get_admin_fallback() -> dict:
    global _admin_fallback
    if _admin_fallback is None:
        _admin_fallback = {
            "user_id": "admin",
            "username": "admin",
            "password_hash": _hash_password(_admin_password()),
            "active": True,
        }
    return _admin_fallback


def _get_pool_lock() -> asyncio.Lock:
    global _pool_lock
    if _pool_lock is None:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def _get_pool() -> Optional[AsyncConnectionPool]:
    global _pool, _pool_unavailable
    if settings.environment == "test":
        return None
    # Item 9: circuit breaker — skip connection attempt if previously failed
    if _pool_unavailable:
        return None
    if _pool is not None and not _pool.closed:
        return _pool
    async with _get_pool_lock():
        if _pool_unavailable:
            return None
        if _pool is not None and not _pool.closed:
            return _pool
        try:
            conninfo = (
                f"host={settings.db_host} port={settings.db_port} "
                f"dbname={settings.db_name} user={settings.db_user} "
                f"password={settings.db_password} "
                f"connect_timeout=2"  # fast fail; graceful fallback handles the rest
            )
            p = AsyncConnectionPool(
                conninfo,
                min_size=1,
                max_size=5,
                kwargs={"row_factory": dict_row, "autocommit": True},
                open=False,
            )
            await p.open(wait=True, timeout=3)
            _pool = p
            return _pool
        except Exception as exc:
            logger.debug("UserService: DB pool unavailable, using in-memory fallback (%s)", exc)
            _pool_unavailable = True  # Item 9: trip the circuit breaker
            return None


def reset_pool() -> None:
    """Item 9: Reset the circuit breaker so the pool can be re-tested (e.g. on health checks)."""
    global _pool, _pool_unavailable
    _pool_unavailable = False
    _pool = None


class UserService:
    """Async user service backed by ``kotte_users``."""

    async def authenticate(self, username: str, password: str) -> Optional[dict]:
        pool = await _get_pool()
        if pool is None:
            if settings.environment == "test" or settings.allow_admin_fallback:
                return self._authenticate_fallback(username, password)
            raise APIException(
                code=ErrorCode.DB_UNAVAILABLE,
                message="Authentication service unavailable",
                category=ErrorCategory.UPSTREAM,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT id, username, password_hash FROM kotte_users WHERE username = %s",
                    (username,),
                )
                row = await cur.fetchone()
                if row is None:
                    logger.warning("Authentication failed: user '%s' not found", username)
                    return None
                row_dict = cast(dict[str, Any], row)
                if not _verify_password(password, row_dict["password_hash"]):
                    logger.warning("Authentication failed: invalid password for '%s'", username)
                    return None
                await conn.execute(
                    "UPDATE kotte_users SET last_login_at = %s WHERE id = %s",
                    (datetime.now(timezone.utc), row_dict["id"]),
                )
            logger.info("User '%s' authenticated successfully", username)
            return {"user_id": str(row_dict["id"]), "username": row_dict["username"]}
        except APIException:
            raise
        except Exception as exc:
            logger.warning("UserService.authenticate DB error: %s", exc)
            if settings.environment == "test" or settings.allow_admin_fallback:
                return self._authenticate_fallback(username, password)
            raise APIException(
                code=ErrorCode.DB_UNAVAILABLE,
                message="Authentication service unavailable",
                category=ErrorCategory.UPSTREAM,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

    def _authenticate_fallback(self, username: str, password: str) -> Optional[dict]:
        admin = _get_admin_fallback()
        if username != admin["username"]:
            return None
        if not _verify_password(password, admin["password_hash"]):
            return None
        return {"user_id": admin["user_id"], "username": admin["username"]}

    async def get_user(self, user_id: str) -> Optional[dict]:
        pool = await _get_pool()
        if pool is None:
            if settings.environment == "test" or settings.allow_admin_fallback:
                return self._get_user_fallback(user_id)
            return None
        try:
            if user_id.isdigit():
                async with pool.connection() as conn:
                    cur = await conn.execute(
                        "SELECT id, username FROM kotte_users WHERE id = %s",
                        (int(user_id),),
                    )
                    row = await cur.fetchone()
                if row:
                    row_dict = cast(dict[str, Any], row)
                    return {"user_id": str(row_dict["id"]), "username": row_dict["username"]}
        except Exception as exc:
            logger.warning("UserService.get_user DB error: %s", exc)
            if settings.environment == "test" or settings.allow_admin_fallback:
                return self._get_user_fallback(user_id)
        return (
            self._get_user_fallback(user_id)
            if settings.allow_admin_fallback or settings.environment == "test"
            else None
        )

    def _get_user_fallback(self, user_id: str) -> Optional[dict]:
        admin = _get_admin_fallback()
        if user_id == admin["user_id"]:
            return {"user_id": admin["user_id"], "username": admin["username"]}
        return None

    async def create_user(self, username: str, password: str) -> dict:
        pool = await _get_pool()
        if pool is None:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Database unavailable; cannot create users",
                category=ErrorCategory.UPSTREAM,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            password_hash = _hash_password(password)
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "INSERT INTO kotte_users (username, password_hash) VALUES (%s, %s)"
                    " RETURNING id, username",
                    (username, password_hash),
                )
                row = await cur.fetchone()
            logger.info("Created user '%s'", username)
            row_dict = cast(dict[str, Any], row)
            return {"user_id": str(row_dict["id"]), "username": row_dict["username"]}
        except psycopg.errors.UniqueViolation:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"User '{username}' already exists",
                category=ErrorCategory.CONFLICT,
                status_code=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            logger.warning("UserService.create_user DB error: %s", exc)
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="User creation failed due to a service error",
                category=ErrorCategory.UPSTREAM,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> None:
        pool = await _get_pool()
        if pool is None:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Database unavailable",
                category=ErrorCategory.UPSTREAM,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if not user_id.isdigit():
            raise APIException(
                code=ErrorCode.AUTH_INVALID_SESSION,
                message="Cannot change password for built-in accounts via this endpoint",
                category=ErrorCategory.AUTHENTICATION,
                status_code=status.HTTP_403_FORBIDDEN,
            )
        async with pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, password_hash FROM kotte_users WHERE id = %s",
                (int(user_id),),
            )
            row = await cur.fetchone()
            if row is None:
                raise APIException(
                    code=ErrorCode.AUTH_INVALID_SESSION,
                    message="User not found",
                    category=ErrorCategory.AUTHENTICATION,
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            row_dict = cast(dict[str, Any], row)
            if not _verify_password(old_password, row_dict["password_hash"]):
                raise APIException(
                    code=ErrorCode.AUTH_INVALID_SESSION,
                    message="Current password is incorrect",
                    category=ErrorCategory.AUTHENTICATION,
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )
            new_hash = _hash_password(new_password)
            await conn.execute(
                "UPDATE kotte_users SET password_hash = %s WHERE id = %s",
                (new_hash, row_dict["id"]),
            )

    async def seed_admin(self) -> None:
        """Insert the admin user if kotte_users is empty. Called from app lifespan."""
        pool = await _get_pool()
        if pool is None:
            logger.info("UserService: no DB pool; admin user served from memory")
            return
        try:
            async with pool.connection() as conn:
                cur = await conn.execute("SELECT COUNT(*) AS n FROM kotte_users")
                row = await cur.fetchone()
                row_dict = cast(dict[str, Any], row) if row is not None else None
                if row_dict and row_dict["n"] == 0:
                    password_hash = _hash_password(_admin_password())
                    await conn.execute(
                        "INSERT INTO kotte_users (username, password_hash) VALUES (%s, %s)"
                        " ON CONFLICT (username) DO NOTHING",
                        ("admin", password_hash),
                    )
                    logger.info("Seeded default admin user into kotte_users")
        except Exception as exc:
            logger.warning("UserService.seed_admin failed (migrations may not have run): %s", exc)

    async def close(self) -> None:
        global _pool
        if _pool is not None and not _pool.closed:
            await _pool.close()
            _pool = None


user_service = UserService()
