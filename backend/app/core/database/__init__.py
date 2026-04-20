"""Database connection management (Facade)."""

import logging
from typing import Optional

import psycopg

from app.core.database.connection import DatabaseConnection as BaseConnection
from app.core.database.cypher import CypherExecutor
from app.core.database.manager import QueryManager
from app.core.database.utils import cypher_return_columns as _crc, split_top_level_commas as _stlc

logger = logging.getLogger(__name__)


class DatabaseConnection(BaseConnection):
    """
    Manages a PostgreSQL connection with Apache AGE.

    This class acts as a facade, delegating specialized tasks to focused components
    while maintaining the original interface for backward compatibility.
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
        super().__init__(host, port, database, user, password, sslmode)
        self._cypher_executor = CypherExecutor(self)
        self._query_manager = QueryManager(self)

    @staticmethod
    def _cypher_return_columns(cypher_query: str) -> list[str]:
        """Backward compatible access to cypher_return_columns."""
        return _crc(cypher_query)

    @staticmethod
    def _split_top_level_commas(s: str) -> Optional[list[str]]:
        """Backward compatible access to split_top_level_commas."""
        return _stlc(s)

    async def get_backend_pid(
        self, conn: Optional[psycopg.AsyncConnection] = None
    ) -> Optional[int]:
        """Get the backend PID for this connection or a provided pool handle."""
        return await self._query_manager.get_backend_pid(conn)

    async def cancel_backend(self, pid: int) -> bool:
        """Cancel a PostgreSQL backend process."""
        return await self._query_manager.cancel_backend(pid)

    async def get_query_pid(self, query_text: Optional[str] = None) -> Optional[int]:
        """Get the backend PID for a running query."""
        return await self._query_manager.get_query_pid(query_text)

    async def execute_cypher(
        self,
        graph_name: str,
        cypher_query: str,
        params: Optional[dict] = None,
        time_limit_seconds: Optional[int] = None,
        *,
        conn: Optional[psycopg.AsyncConnection] = None,
    ) -> list[dict]:
        """Execute a Cypher query via Apache AGE."""
        return await self._cypher_executor.execute_cypher(
            graph_name, cypher_query, params, time_limit_seconds, conn=conn
        )
