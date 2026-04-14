"""Core database connection management with pooling support."""

import asyncio
import hashlib
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

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

        # Pool configure callbacks must return connections in IDLE state.
        # SELECT/SET open a transaction under default psycopg settings.
        await conn.commit()

    async def _report_pool_metrics(self) -> None:
        """Background task to report pool metrics."""
        consecutive_failures = 0
        while self._pool:
            try:
                stats = self._pool.get_stats()
                # AsyncConnectionPool stats have different attributes than ConnectionPool
                total = stats.get("pool_size", 0)
                available = stats.get("pool_available", 0)
                in_use = total - available
                metrics.record_db_pool_stats(self.database, total, available, in_use)
                consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                consecutive_failures += 1
                # Avoid log spam: full traceback on first failure, then periodic warnings.
                if consecutive_failures == 1:
                    logger.warning(
                        "Pool metrics report failed (will retry every 30s): %s",
                        e,
                        exc_info=True,
                    )
                elif consecutive_failures % 10 == 0:
                    logger.warning(
                        "Pool metrics still failing after %s consecutive errors: %s",
                        consecutive_failures,
                        e,
                    )
            await asyncio.sleep(30)

    async def connect(self) -> None:
        """Initialize the connection pool."""
        pool: Optional[AsyncConnectionPool] = None
        try:
            pool = AsyncConnectionPool(
                kwargs=self._connect_kwargs(),
                min_size=settings.db_pool_min_size,
                max_size=settings.db_pool_max_size,
                max_idle=settings.db_pool_max_idle,
                timeout=settings.db_connect_timeout,
                configure=self._configure_age,
                open=False,
            )
            await pool.open()
            await pool.wait()

            self._pool = pool
            pool = None

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
        finally:
            if pool is not None:
                try:
                    await pool.close()
                except Exception as cleanup_err:
                    logger.warning(
                        "Failed to close partially initialized pool: %s",
                        cleanup_err,
                        exc_info=True,
                    )

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

    async def _execute_query_on_conn(
        self,
        conn: psycopg.AsyncConnection,
        query: str,
        params: Optional[dict],
        time_limit_seconds: int,
        start_time: float,
        *,
        rollback_on_error: bool = True,
    ) -> list[dict]:
        async with conn.cursor() as cur:
            try:
                await asyncio.wait_for(
                    cur.execute(query, params),
                    timeout=time_limit_seconds,
                )
                result = await cur.fetchall()
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                return result
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
                logger.warning(
                    "Query timeout (hash: %s) after %s seconds",
                    query_hash,
                    time_limit_seconds,
                )
                if rollback_on_error:
                    await conn.rollback()
                raise
            except Exception:
                query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
                logger.error("execute_query failed (hash: %s)", query_hash, exc_info=True)
                if rollback_on_error:
                    await conn.rollback()
                raise

    async def execute_query(
        self,
        query: str,
        params: Optional[dict] = None,
        time_limit_seconds: Optional[int] = None,
        *,
        conn: Optional[psycopg.AsyncConnection] = None,
    ) -> list[dict]:
        """
        Execute a query. Uses ``conn`` when provided (e.g. inside ``transaction()``);
        otherwise checks out a connection from the pool.
        """
        if time_limit_seconds is None:
            time_limit_seconds = settings.query_timeout
        start_time = time.time()
        if conn is not None:
            return await self._execute_query_on_conn(
                conn, query, params, time_limit_seconds, start_time, rollback_on_error=False
            )
        async with self.connection() as ac:
            return await self._execute_query_on_conn(
                ac, query, params, time_limit_seconds, start_time
            )

    async def _execute_command_on_conn(
        self,
        conn: psycopg.AsyncConnection,
        query: str,
        params: Optional[dict],
        time_limit_seconds: int,
        start_time: float,
        *,
        rollback_on_error: bool = True,
    ) -> None:
        async with conn.cursor() as cur:
            try:
                await asyncio.wait_for(
                    cur.execute(query, params),
                    timeout=time_limit_seconds,
                )
                duration = time.time() - start_time
                metrics.record_db_query(duration)
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                metrics.record_db_query(duration)
                query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
                logger.warning(
                    "Command timeout (hash: %s) after %s seconds",
                    query_hash,
                    time_limit_seconds,
                )
                if rollback_on_error:
                    await conn.rollback()
                raise
            except Exception:
                query_hash = hashlib.sha256(query.encode()).hexdigest()[:8]
                logger.error(
                    "execute_command failed (hash: %s)", query_hash, exc_info=True
                )
                if rollback_on_error:
                    await conn.rollback()
                raise

    async def execute_command(
        self,
        query: str,
        params: Optional[dict] = None,
        time_limit_seconds: Optional[int] = None,
        *,
        conn: Optional[psycopg.AsyncConnection] = None,
    ) -> None:
        """Execute a command (no result set). Pass ``conn`` to join an open transaction."""
        if time_limit_seconds is None:
            time_limit_seconds = settings.query_timeout
        start_time = time.time()
        if conn is not None:
            await self._execute_command_on_conn(
                conn, query, params, time_limit_seconds, start_time, rollback_on_error=False
            )
            return
        async with self.connection() as ac:
            await self._execute_command_on_conn(ac, query, params, time_limit_seconds, start_time)

    async def _execute_scalar_on_conn(
        self,
        conn: psycopg.AsyncConnection,
        query: str,
        params: Optional[dict],
        time_limit_seconds: int,
        *,
        rollback_on_error: bool = True,
    ) -> Optional[Any]:
        start_clock = time.time()
        async with conn.cursor() as cur:
            try:
                await asyncio.wait_for(
                    cur.execute(query, params), timeout=time_limit_seconds
                )
                result = await cur.fetchone()
                metrics.record_db_query(time.time() - start_clock)
                return first_value(result)
            except Exception:
                if rollback_on_error:
                    await conn.rollback()
                raise

    async def execute_scalar(
        self,
        query: str,
        params: Optional[dict] = None,
        *,
        time_limit_seconds: Optional[int] = None,
        conn: Optional[psycopg.AsyncConnection] = None,
    ) -> Optional[Any]:
        """Execute a query and return a single scalar value."""
        if time_limit_seconds is None:
            time_limit_seconds = settings.query_timeout
        if conn is not None:
            return await self._execute_scalar_on_conn(
                conn, query, params, time_limit_seconds, rollback_on_error=False
            )
        async with self.connection() as ac:
            try:
                return await self._execute_scalar_on_conn(
                    ac, query, params, time_limit_seconds
                )
            except Exception:
                await ac.rollback()
                raise

    @asynccontextmanager
    async def transaction(self, time_limit_seconds: Optional[int] = None):
        """
        Context manager for database transactions with guaranteed resource cleanup.
        """
        effective_timeout = time_limit_seconds if time_limit_seconds is not None else 60

        try:
            async with asyncio.timeout(effective_timeout):
                async with self.connection() as conn:
                    # psycopg's transaction() context manager handles BEGIN/COMMIT/ROLLBACK
                    async with conn.transaction():
                        try:
                            async with conn.cursor() as cur:
                                # Also set a server-side timeout as a second line of defense
                                timeout_ms = str(int(effective_timeout * 1000))
                                await cur.execute(
                                    "SELECT set_config('statement_timeout', %(timeout_ms)s, true)",
                                    {"timeout_ms": timeout_ms},
                                )
                        except Exception as e:
                            logger.warning(f"Failed to set transaction statement_timeout: {e}")

                        yield conn
        except TimeoutError:
            logger.warning(
                "Transaction or connection acquisition timed out after %s seconds",
                effective_timeout,
            )
            raise
