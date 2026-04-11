"""Query management and backend process control."""

import asyncio
import logging
from typing import Optional

import psycopg

from app.core.config import settings
from app.core.database.utils import first_value

logger = logging.getLogger(__name__)

_SQL_BACKEND_PID = "SELECT pg_backend_pid()"


class QueryManager:
    """Manages database backend processes and query cancellation."""

    def __init__(self, db_conn):
        self.db_conn = db_conn

    async def _fetch_backend_pid(self, conn: psycopg.AsyncConnection) -> Optional[int]:
        async with conn.cursor() as cur:
            await cur.execute(_SQL_BACKEND_PID)
            result = await cur.fetchone()
            return first_value(result)

    async def get_backend_pid(
        self, conn: Optional[psycopg.AsyncConnection] = None
    ) -> Optional[int]:
        """
        Return ``pg_backend_pid()`` for the given connection, or check out the pool
        when ``conn`` is omitted. Pass ``conn`` when it is the same handle used for
        the query being tracked or cancelled.

        When ``conn`` is omitted, a pooled connection is borrowed briefly; the PID is
        for that checkout, not a caller-specific “sticky” session. For cancellation
        or correlation with an in-flight statement, pass the same ``AsyncConnection``
        used for that work.
        """
        try:
            if conn is not None:
                return await self._fetch_backend_pid(conn)
            async with self.db_conn.connection() as pooled:
                return await self._fetch_backend_pid(pooled)
        except Exception as e:
            logger.warning(f"Failed to get backend PID: {e}")
            return None

    async def cancel_backend(self, pid: int) -> bool:
        """
        Cancel a PostgreSQL backend process.
        
        Requires a separate connection to perform the cancellation.
        """
        try:
            # Create a temporary connection for cancellation
            cancel_conn = await asyncio.wait_for(
                psycopg.AsyncConnection.connect(**self.db_conn._connect_kwargs()),
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

    async def get_query_pid(self, query_text: Optional[str] = None) -> Optional[int]:
        """
        Match a running query in ``pg_stat_activity`` for a backend session.

        Reads ``pg_backend_pid()`` on one checkout, then queries ``pg_stat_activity``
        from a **second** connection so the monitored row's ``query`` field is not
        replaced by the lookup statement itself.
        """
        try:
            async with self.db_conn.connection() as target_conn:
                current_pid = await self._fetch_backend_pid(target_conn)
            if not current_pid:
                return None

            find_query = """
                SELECT pid
                FROM pg_stat_activity
                WHERE pid = %(pid)s
                  AND state = 'active'
                  AND query_start IS NOT NULL
            """
            params: dict = {"pid": current_pid}

            if query_text:
                find_query += " AND query LIKE %(query_text)s"
                params["query_text"] = f"%{query_text}%"

            find_query += " LIMIT 1"

            async with self.db_conn.connection() as probe_conn:
                async with probe_conn.cursor() as cur:
                    await cur.execute(find_query, params)
                    result = await cur.fetchone()
                    return first_value(result)
        except Exception as e:
            logger.warning(f"Failed to get query PID: {e}")
            return None
