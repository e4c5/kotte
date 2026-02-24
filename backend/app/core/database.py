"""Database connection management."""

import asyncio
import re
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics
from app.core.validation import validate_graph_name

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
            cancel_conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(**self._connect_kwargs()),
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
        except Exception:
            logger.error("Failed to cancel backend PID %s", pid)
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

    @staticmethod
    def _split_top_level_commas(s: str) -> Optional[List[str]]:
        """Split s by commas only at top level (not inside (), [], {}, or strings).
        Returns None if quotes or brackets are unbalanced (ambiguous input)."""
        parts: List[str] = []
        cur: List[str] = []
        depth_p, depth_b, depth_br = 0, 0, 0
        in_sq, in_dq = False, False
        i = 0
        while i < len(s):
            c = s[i]
            if in_sq:
                if c == "'" and (i == 0 or s[i - 1] != "\\"):
                    in_sq = False
                cur.append(c)
                i += 1
                continue
            if in_dq:
                if c == '"' and (i == 0 or s[i - 1] != "\\"):
                    in_dq = False
                cur.append(c)
                i += 1
                continue
            if c == "'":
                in_sq = True
                cur.append(c)
                i += 1
                continue
            if c == '"':
                in_dq = True
                cur.append(c)
                i += 1
                continue
            if c == "(":
                depth_p += 1
            elif c == ")":
                depth_p -= 1
                if depth_p < 0:
                    return None
            elif c == "[":
                depth_b += 1
            elif c == "]":
                depth_b -= 1
                if depth_b < 0:
                    return None
            elif c == "{":
                depth_br += 1
            elif c == "}":
                depth_br -= 1
                if depth_br < 0:
                    return None
            elif (
                c == ","
                and depth_p == 0
                and depth_b == 0
                and depth_br == 0
            ):
                parts.append("".join(cur).strip())
                cur = []
                i += 1
                continue
            cur.append(c)
            i += 1
        if in_sq or in_dq or depth_p != 0 or depth_b != 0 or depth_br != 0:
            return None
        parts.append("".join(cur).strip())
        return parts

    @staticmethod
    def _cypher_return_columns(cypher_query: str) -> List[str]:
        """
        Infer RETURN column names from Cypher so we can build AS (col1 agtype, ...).
        AGE requires the AS clause to match the return column count and names.
        """
        # Find RETURN ... up to ORDER BY, LIMIT, SKIP, or end
        m = re.search(
            r"\bRETURN\s+(.+?)(?=\s+ORDER\s+BY|\s+LIMIT|\s+SKIP|\s*;|\s*$)",
            cypher_query,
            re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return ["result"]
        return_expr = m.group(1).strip()
        parts = DatabaseConnection._split_top_level_commas(return_expr)
        if parts is None:
            return ["result"]
        names: List[str] = []
        for i, part in enumerate(parts):
            # Prefer "AS alias"
            as_match = re.search(r"\s+AS\s+(\w+)\s*$", part, re.IGNORECASE)
            if as_match:
                name = as_match.group(1)
            else:
                name = f"c{i + 1}"
            # Safe identifier: alphanumeric and underscore only
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
                names.append(name)
            else:
                names.append(f"c{i + 1}")
        return names if names else ["result"]

    async def execute_cypher(
        self,
        graph_name: str,
        cypher_query: str,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """
        Execute a Cypher query via Apache AGE using bound parameters.
        When there are no Cypher parameters we use the 2-arg cypher(graph, query) form;
        when params are present we use the 3-arg form with a bound agtype parameter.
        A trailing semicolon is stripped before sending to AGE, which does not expect it.
        """
        validated_graph_name = validate_graph_name(graph_name)
        cypher_normalized = cypher_query.rstrip()
        if cypher_normalized.endswith(";"):
            cypher_normalized = cypher_normalized[:-1].rstrip()
        has_params = bool(params)
        json_mod = __import__("json")
        params_json = json_mod.dumps(params) if has_params else "null"

        # AGE requires AS (col1 agtype, ...) to match RETURN column count and names
        return_cols = self._cypher_return_columns(cypher_query)
        as_clause = sql.SQL(", ").join(
            sql.Identifier(c) + sql.SQL(" agtype") for c in return_cols
        )

        if has_params:
            query_composed = sql.SQL(
                "SELECT * FROM ag_catalog.cypher({graph_name}::text, {cypher}::text, {params}::agtype) AS ({as_clause})"
            ).format(
                graph_name=sql.Placeholder("graph_name"),
                cypher=sql.Placeholder("cypher"),
                params=sql.Placeholder("params"),
                as_clause=as_clause,
            )
            run_params: Optional[dict] = {
                "graph_name": validated_graph_name,
                "cypher": cypher_normalized,
                "params": params_json,
            }
        else:
            query_composed = sql.SQL(
                "SELECT * FROM ag_catalog.cypher({graph_name}::text, {cypher}::text) AS ({as_clause})"
            ).format(
                graph_name=sql.Placeholder("graph_name"),
                cypher=sql.Placeholder("cypher"),
                as_clause=as_clause,
            )
            run_params = {
                "graph_name": validated_graph_name,
                "cypher": cypher_normalized,
            }

        logger.info(
            "execute_cypher: graph=%s, user cypher (verbatim): %s",
            validated_graph_name,
            cypher_query,
        )
        logger.info("execute_cypher: params: %s", run_params)

        try:
            return await self.execute_query(query_composed, run_params, timeout=timeout)
        except Exception:
            logger.error(
                "execute_cypher: query failed; params: %s",
                run_params,
                exc_info=True,
            )
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


# Connection pool per session (stored in session manager)
# This is a simplified approach; for production, consider connection pooling library
