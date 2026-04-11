"""Core database connection management."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics
from app.core.database.utils import first_value

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

    def _connect_kwargs(self) -> dict:
        """Build psycopg connection kwargs without embedding secrets in a DSN string."""
        kwargs = {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": settings.db_connect_timeout,
            "row_factory": dict_row,
        }
        if self.sslmode:
            kwargs["sslmode"] = self.sslmode
        return kwargs

    async def connect(self) -> None:
        """Establish database connection."""
        try:
            self._conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(**self._connect_kwargs()),
                timeout=settings.db_connect_timeout,
            )

            # Verify AGE extension and configure session for AGE
            async with self._conn.cursor() as cur:
                await cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'age')"
                )
                result = await cur.fetchone()
                if not result or not result.get("exists"):
                    raise APIException(
                        code=ErrorCode.DB_UNAVAILABLE,
                        message="Apache AGE extension not found in database",
                        category=ErrorCategory.UPSTREAM,
                        status_code=500,
                    )
                # Per Apache AGE docs, for every connection we must load AGE and set search_path.
                # See: https://age.apache.org/getstarted/quickstart/ (Post Installation)
                await cur.execute("LOAD 'age'")
                await cur.execute('SET search_path = ag_catalog, "$user", public')
            await self._conn.commit()

            logger.info(
                f"Connected to database {self.database} on {self.host}:{self.port}"
            )
        except asyncio.TimeoutError as e:
            logger.error(
                "Database connection timed out after %s seconds",
                settings.db_connect_timeout,
            )
            raise APIException(
                code=ErrorCode.DB_CONNECT_FAILED,
                message=(
                    "Failed to connect to database: "
                    f"connection timed out after {settings.db_connect_timeout}s"
                ),
                category=ErrorCategory.UPSTREAM,
                status_code=500,
                retryable=True,
            ) from e
        except psycopg.Error as e:
            logger.error("Database connection failed", exc_info=True)
            raise APIException(
                code=ErrorCode.DB_CONNECT_FAILED,
                message="Failed to connect to database",
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
        self, query: str, params: Optional[dict] = None, timeout: Optional[int] = None
    ) -> list[dict]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            timeout: Query timeout in seconds (uses settings.query_timeout if None)
        """
        if timeout is None:
            timeout = settings.query_timeout
        start_time = time.time()
        async with self.connection.cursor() as cur:
            try:
                # Execute with timeout
                await asyncio.wait_for(
                    cur.execute(query, params),
                    timeout=timeout,
                )
                result = await cur.fetchall()
                # Record query duration
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                return result
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                logger.warning(f"Query timeout after {timeout} seconds")
                await self._conn.rollback()
                raise
            except Exception:
                logger.error(
                    "execute_query failed; full SQL: %s",
                    query,
                    exc_info=True,
                )
                logger.error("execute_query failed; params: %s", params)
                await self._conn.rollback()
                raise

    async def execute_command(
        self, query: str, params: Optional[dict] = None, timeout: Optional[int] = None
    ) -> None:
        """
        Execute a command that returns no result set (e.g. ANALYZE, DDL).
        Do not use for SELECT or commands with RETURNING.
        """
        if timeout is None:
            timeout = settings.query_timeout
        start_time = time.time()
        async with self.connection.cursor() as cur:
            try:
                await asyncio.wait_for(
                    cur.execute(query, params),
                    timeout=timeout,
                )
                duration = time.time() - start_time
                metrics.record_db_query(duration)
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                logger.warning(f"Command timeout after {timeout} seconds")
                raise

    async def execute_scalar(
        self, query: str, params: Optional[dict] = None
    ) -> Optional[any]:
        """Execute a query and return a single scalar value."""
        try:
            async with self.connection.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return first_value(result)
        except Exception:
            if self._conn:
                await self._conn.rollback()
            raise

    @asynccontextmanager
    async def transaction(self, timeout: Optional[int] = None):
        """
        Context manager for database transactions.

        Args:
            timeout: Optional transaction timeout in seconds. If not provided,
                     a sensible default is used to prevent long-running transactions.
        """
        # Default to 60s for transaction-scoped timeout to avoid long locks
        if timeout is None:
            effective_timeout = 60
        else:
            effective_timeout = timeout
        async with self.connection.transaction():
            try:
                # Apply a statement timeout for all statements in this transaction
                async with self.connection.cursor() as cur:
                    await cur.execute(
                        f"SET LOCAL statement_timeout = {effective_timeout * 1000}"
                    )
            except Exception as e:
                logger.warning(f"Failed to set transaction statement_timeout: {e}")
            yield
