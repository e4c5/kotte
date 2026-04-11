"""Core database connection management with pooling support."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics
from app.core.database.utils import first_value

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Manages a PostgreSQL connection pool with Apache AGE support.
    One instance per user session.
    """

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
        self._pool: Optional[AsyncConnectionPool] = None
        self._metrics_task: Optional[asyncio.Task] = None

    def _connect_kwargs(self) -> dict:
        """Build psycopg connection kwargs."""
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

    async def _configure_age(self, conn: psycopg.AsyncConnection) -> None:
        """Configure a connection for Apache AGE. Mandatory for every connection in the pool."""
        async with conn.cursor() as cur:
            # Verify AGE extension
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
            await cur.execute("LOAD 'age'")
            await cur.execute('SET search_path = ag_catalog, "$user", public')

    async def _report_pool_metrics(self) -> None:
        """Background task to report pool metrics."""
        while self._pool:
            try:
                stats = self._pool.get_stats()
                # AsyncConnectionPool stats have different attributes than ConnectionPool
                # We'll use the available info
                total = stats.get("pool_size", 0)
                available = stats.get("pool_available", 0)
                in_use = total - available
                metrics.record_db_pool_stats(self.database, total, available, in_use)
            except Exception:
                # Don't let metrics reporting crash the session
                pass
            await asyncio.sleep(30)

    async def connect(self) -> None:
        """Initialize the connection pool."""
        try:
            self._pool = AsyncConnectionPool(
                kwargs=self._connect_kwargs(),
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                max_idle=settings.db_pool_max_idle,
                timeout=settings.db_connect_timeout,
                configure=self._configure_age,
                open=False,
            )
            await self._pool.open()
            await self._pool.wait()

            logger.info(
                f"Connection pool initialized for {self.database} on {self.host}:{self.port} "
                f"(size: {settings.db_pool_min_size}-{settings.db_pool_max_size})"
            )
            
            # Start metrics reporting
            self._metrics_task = asyncio.create_task(self._report_pool_metrics())
            
        except asyncio.TimeoutError as e:
            logger.error(
                "Database pool initialization timed out after %s seconds",
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
        except Exception as e:
            logger.error("Database connection failed", exc_info=True)
            if isinstance(e, APIException):
                raise
            raise APIException(
                code=ErrorCode.DB_CONNECT_FAILED,
                message=f"Failed to connect to database: {str(e)}",
                category=ErrorCategory.UPSTREAM,
                status_code=500,
                retryable=True,
            ) from e

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._metrics_task:
            self._metrics_task.cancel()
            self._metrics_task = None
            
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info(f"Connection pool for {self.database} closed")

    @asynccontextmanager
    async def connection(self):
        """Context manager to get a connection from the pool."""
        if not self._pool:
            raise APIException(
                code=ErrorCode.DB_UNAVAILABLE,
                message="Database connection pool not initialized",
                category=ErrorCategory.UPSTREAM,
                status_code=500,
            )
        async with self._pool.connection() as conn:
            yield conn

    async def execute_query(
        self, query: str, params: Optional[dict] = None, timeout: Optional[int] = None
    ) -> list[dict]:
        """Execute a query using a connection from the pool."""
        if timeout is None:
            timeout = settings.query_timeout
        start_time = time.time()
        
        async with self.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await asyncio.wait_for(
                        cur.execute(query, params),
                        timeout=timeout,
                    )
                    result = await cur.fetchall()
                    duration = time.time() - start_time
                    metrics.record_db_query(duration)
                    return result
                except asyncio.TimeoutError:
                    duration = time.time() - start_time
                    metrics.record_db_query(duration)
                    logger.warning(f"Query timeout after {timeout} seconds")
                    await conn.rollback()
                    raise
                except Exception:
                    logger.error("execute_query failed; full SQL: %s", query, exc_info=True)
                    await conn.rollback()
                    raise

    async def execute_command(
        self, query: str, params: Optional[dict] = None, timeout: Optional[int] = None
    ) -> None:
        """Execute a command (no result set) using a connection from the pool."""
        if timeout is None:
            timeout = settings.query_timeout
        start_time = time.time()
        
        async with self.connection() as conn:
            async with conn.cursor() as cur:
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
            async with self.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    result = await cur.fetchone()
                    return first_value(result)
        except Exception:
            raise

    @asynccontextmanager
    async def transaction(self, timeout: Optional[int] = None):
        """Context manager for database transactions."""
        if timeout is None:
            effective_timeout = 60
        else:
            effective_timeout = timeout
            
        async with self.connection() as conn:
            async with conn.transaction():
                try:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            f"SET LOCAL statement_timeout = {effective_timeout * 1000}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to set transaction statement_timeout: {e}")
                yield
