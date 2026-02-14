"""Database connection management."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages a PostgreSQL connection with Apache AGE."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        sslmode: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.sslmode = sslmode
        self._conn: Optional[psycopg.AsyncConnection] = None

    async def connect(self) -> None:
        """Establish database connection."""
        try:
            conn_str = (
                f"host={self.host} port={self.port} "
                f"dbname={self.database} user={self.user} "
                f"password={self.password}"
            )
            if self.sslmode:
                conn_str += f" sslmode={self.sslmode}"

            self._conn = await psycopg.AsyncConnection.connect(
                conn_str, row_factory=dict_row
            )

            # Verify AGE extension
            async with self._conn.cursor() as cur:
                await cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'age')"
                )
                result = await cur.fetchone()
                if not result or not result["exists"]:
                    raise APIException(
                        code=ErrorCode.DB_UNAVAILABLE,
                        message="Apache AGE extension not found in database",
                        category=ErrorCategory.UPSTREAM,
                        status_code=500,
                    )

            logger.info(
                f"Connected to database {self.database} on {self.host}:{self.port}"
            )
        except psycopg.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise APIException(
                code=ErrorCode.DB_CONNECT_FAILED,
                message=f"Failed to connect to database: {str(e)}",
                category=ErrorCategory.UPSTREAM,
                status_code=500,
                retryable=True,
            ) from e

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    @property
    def connection(self) -> psycopg.AsyncConnection:
        """Get the connection object."""
        if not self._conn:
            raise APIException(
                code=ErrorCode.DB_UNAVAILABLE,
                message="Database connection not established",
                category=ErrorCategory.UPSTREAM,
                status_code=500,
            )
        return self._conn

    async def execute_query(
        self, query: str, params: Optional[dict] = None
    ) -> list[dict]:
        """Execute a query and return results."""
        async with self.connection.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()

    async def execute_scalar(
        self, query: str, params: Optional[dict] = None
    ) -> Optional[any]:
        """Execute a query and return a single scalar value."""
        async with self.connection.cursor() as cur:
            await cur.execute(query, params)
            result = await cur.fetchone()
            return result[0] if result else None

    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        async with self.connection.transaction():
            yield


# Connection pool per session (stored in session manager)
# This is a simplified approach; for production, consider connection pooling library

