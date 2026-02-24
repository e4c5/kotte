"""Shared FastAPI dependency functions."""

from fastapi import Depends

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory


async def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
    """Return the active :class:`DatabaseConnection` stored in the current session.

    Raises a 500 :class:`APIException` when no connection has been established yet.
    """
    db_conn = session.get("db_connection")
    if not db_conn:
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message="Database connection not established",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        )
    return db_conn
