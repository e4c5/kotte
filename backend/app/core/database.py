"""Database connection management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics

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
        self, query: str, params: Optional[dict] = None, timeout: Optional[int] = None
    ) -> list[dict]:
        """
        Execute a query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            timeout: Query timeout in seconds (uses settings.query_timeout if None)
        """
        timeout = timeout or settings.query_timeout
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
                raise APIException(
                    code=ErrorCode.QUERY_TIMEOUT,
                    message=f"Query execution timed out after {timeout} seconds",
                    category=ErrorCategory.UPSTREAM,
                    status_code=504,
                    retryable=True,
                ) from None

    async def get_backend_pid(self) -> Optional[int]:
        """
        Get the backend PID for this connection.
        
        Returns:
            Backend PID or None if not available
        """
        try:
            async with self.connection.cursor() as cur:
                await cur.execute("SELECT pg_backend_pid()")
                result = await cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.warning(f"Failed to get backend PID: {e}")
            return None

    async def cancel_backend(self, pid: int) -> bool:
        """
        Cancel a PostgreSQL backend process.
        
        Note: We need to use a separate connection to cancel a query,
        as you cannot cancel a query from the same connection that's running it.
        
        Args:
            pid: Backend PID to cancel
            
        Returns:
            True if cancellation was successful
        """
        try:
            # Create a temporary connection for cancellation
            # (can't cancel from the same connection that's running the query)
            conn_str = (
                f"host={self.host} port={self.port} "
                f"dbname={self.database} user={self.user} "
                f"password={self.password}"
            )
            if self.sslmode:
                conn_str += f" sslmode={self.sslmode}"

            cancel_conn = await psycopg.AsyncConnection.connect(
                conn_str, row_factory=dict_row
            )
            try:
                async with cancel_conn.cursor() as cur:
                    await cur.execute("SELECT pg_cancel_backend(%(pid)s)", {"pid": pid})
                    result = await cur.fetchone()
                    cancelled = result[0] if result else False
                    if cancelled:
                        logger.info(f"Successfully cancelled backend PID {pid}")
                    return cancelled
            finally:
                await cancel_conn.close()
        except Exception as e:
            logger.error(f"Failed to cancel backend {pid}: {e}")
            return False

    async def get_query_pid(self, query_text: str) -> Optional[int]:
        """
        Get the backend PID for a running query.
        
        This queries pg_stat_activity to find the PID of a running query.
        Note: This requires the query text to match exactly.
        
        Args:
            query_text: The SQL query text to find
            
        Returns:
            Backend PID or None if not found
        """
        try:
            # Get current backend PID
            current_pid = await self.get_backend_pid()
            if not current_pid:
                return None

            # Query pg_stat_activity for this PID
            find_query = """
                SELECT pid
                FROM pg_stat_activity
                WHERE pid = %(pid)s
                  AND state = 'active'
                  AND query_start IS NOT NULL
                LIMIT 1
            """
            async with self.connection.cursor() as cur:
                await cur.execute(find_query, {"pid": current_pid})
                result = await cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.warning(f"Failed to get query PID: {e}")
            return None

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

