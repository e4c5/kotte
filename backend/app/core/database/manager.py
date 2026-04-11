"""Query management and backend process control."""

import asyncio
import logging
from typing import Optional

import psycopg

from app.core.config import settings
from app.core.database.utils import first_value

logger = logging.getLogger(__name__)


class QueryManager:
    """Manages database backend processes and query cancellation."""

    def __init__(self, db_conn):
        self.db_conn = db_conn

    async def get_backend_pid(self) -> Optional[int]:
        """
        Return the backend PID for a connection checked out from the pool.

        Each call uses a pooled connection; the PID identifies that checkout, not
        necessarily the same physical session as another operation. For cancellation
        or correlation, pair with the connection used for the active query when
        possible.
        """
        try:
            async with self.db_conn.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT pg_backend_pid()")
                    result = await cur.fetchone()
                    return first_value(result)
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
        Get the backend PID for a running query by matching its text in pg_stat_activity.
        If query_text is None, returns the current backend PID if active.
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
            """
            params = {"pid": current_pid}
            
            if query_text:
                find_query += " AND query LIKE %(query_text)s"
                # Use partial match as Cypher is often wrapped in SELECT * FROM ag_catalog.cypher(...)
                params["query_text"] = f"%{query_text}%"
                
            find_query += " LIMIT 1"
            
            async with self.db_conn.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(find_query, params)
                    result = await cur.fetchone()
                    return first_value(result)
        except Exception as e:
            logger.warning(f"Failed to get query PID: {e}")
            return None
