"""Database connection management."""

import asyncio
import logging
import time
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
                f"password={self.password} "
                f"connect_timeout={settings.db_connect_timeout}"
            )
            if self.sslmode:
                conn_str += f" sslmode={self.sslmode}"

            self._conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row),
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
        if timeout is None:
            timeout = settings.query_timeout
        start_time = time.time()
        async with self.connection.cursor() as cur:
            try:
                # Ensure AGE is loaded and search_path set for this connection (session).
                # Required per Apache AGE docs; running here guarantees it's in effect for this query.
                await cur.execute("LOAD 'age'")
                await cur.execute('SET search_path = ag_catalog, "$user", public')
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
                await cur.execute("LOAD 'age'")
                await cur.execute('SET search_path = ag_catalog, "$user", public')
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
                return self._first_value(result)
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
                f"password={self.password} "
                f"connect_timeout={settings.db_connect_timeout}"
            )
            if self.sslmode:
                conn_str += f" sslmode={self.sslmode}"

            cancel_conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(conn_str, row_factory=dict_row),
                timeout=settings.db_connect_timeout,
            )
            try:
                async with cancel_conn.cursor() as cur:
                    await cur.execute("SELECT pg_cancel_backend(%(pid)s)", {"pid": pid})
                    result = await cur.fetchone()
                    cancelled = (list(result.values())[0] if result else False)
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
                return self._first_value(result)
        except Exception as e:
            logger.warning(f"Failed to get query PID: {e}")
            return None

    def _first_value(self, row: Optional[dict]) -> Optional[any]:
        """Get the first value from a dict row (row_factory=dict_row)."""
        if not row:
            return None
        values = list(row.values())
        return values[0] if values else None

    async def execute_scalar(
        self, query: str, params: Optional[dict] = None
    ) -> Optional[any]:
        """Execute a query and return a single scalar value."""
        try:
            async with self.connection.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return self._first_value(result)
        except Exception:
            if self._conn:
                await self._conn.rollback()
            raise

    def _dollar_quote_tag(self, cypher_query: str) -> str:
        """Pick a dollar-quote tag that does not appear in the query (for safe literal embedding)."""
        for tag in ("$cypher$", "$q$", "$body$", "$x$"):
            if tag not in cypher_query:
                return tag
        # Fallback: use a tag with random suffix so it's unlikely to appear
        import secrets
        return "$c" + secrets.token_hex(4) + "$"

    async def execute_cypher(
        self,
        graph_name: str,
        cypher_query: str,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """
        Execute a Cypher query via Apache AGE using literal SQL (graph and query as literals).
        This matches the AGE docs pattern and avoids overload resolution issues with
        parameterized cypher(...) calls across different AGE versions.
        """
        tag = self._dollar_quote_tag(cypher_query)
        # Graph name is already validated (identifier-safe); escape for SQL literal
        graph_literal = graph_name.replace("'", "''")
        cypher_literal = tag + cypher_query + tag
        # AGE requires the third argument to be a *parameter* (bind), not a literal like NULL::agtype.
        json_mod = __import__("json")
        params_json = json_mod.dumps(params) if params else "null"
        sql = (
            f"SELECT * FROM ag_catalog.cypher("
            f"'{graph_literal}', {cypher_literal}, %(params)s::agtype"
            f") AS (result agtype)"
        )
        run_params: Optional[dict] = {"params": params_json}

        # Log verbatim: user cypher and full generated SQL (so we can copy-paste into psql)
        logger.info("execute_cypher: user cypher (graph=%s) verbatim: %s", graph_name, cypher_query)
        logger.info("execute_cypher: generated SQL verbatim: %s", sql)
        logger.info("execute_cypher: bind params (params)=%s", params_json)

        return await self.execute_query(sql, run_params, timeout=timeout)

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


# Connection pool per session (stored in session manager)
# This is a simplified approach; for production, consider connection pooling library
