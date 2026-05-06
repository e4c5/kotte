"""Cypher query execution logic for Apache AGE.

Dynamic SQL is built only from ``validate_graph_name`` output and parameterized
``%(name)s`` placeholders; the RETURN column list is derived from the Cypher text
for the AGE ``AS (...)`` clause, not from arbitrary user-controlled identifiers.
"""

import hashlib
import logging
import re
from typing import AsyncGenerator, Optional

import psycopg

from app.core.database.utils import cypher_return_columns
from app.core.validation import validate_graph_name

logger = logging.getLogger(__name__)

_SAFE_CURSOR_RE = re.compile(r"^[a-zA-Z_]\w{0,62}$")


def _sanitize_cursor_name(name: str) -> str:
    if not _SAFE_CURSOR_RE.match(name):
        raise ValueError(f"cursor_name must match [a-zA-Z_][a-zA-Z0-9_]{{0,62}}, got: {name!r}")
    return name


class CypherExecutor:
    """Handles Cypher query execution and result parsing for Apache AGE."""

    def __init__(self, db_conn):
        self.db_conn = db_conn

    async def execute_cypher(
        self,
        graph_name: str,
        cypher_query: str,
        params: Optional[dict] = None,
        time_limit_seconds: Optional[int] = None,
        *,
        conn: Optional[psycopg.AsyncConnection] = None,
    ) -> list[dict]:
        """
        Execute a Cypher query via Apache AGE using parameterized SQL.
        A trailing semicolon is stripped before sending to AGE.
        """
        validated_graph_name = validate_graph_name(graph_name)
        cypher_normalized = cypher_query.rstrip()
        if cypher_normalized.endswith(";"):
            cypher_normalized = cypher_normalized[:-1].rstrip()

        # Empty dict {} must use 3-arg cypher() when caller passed params= explicitly
        has_params = params is not None

        # AGE requires AS (col1 agtype, ...) to match RETURN column count and names.
        return_cols = cypher_return_columns(cypher_query)
        as_clause_str = ", ".join(f'"{c}" agtype' for c in return_cols)

        # Build parameterized SQL
        if has_params:
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"%(graph_name)s::text, %(cypher_query)s::text, %(params)s::agtype"
                f") AS ({as_clause_str})"
            )
            run_params = {
                "graph_name": validated_graph_name,
                "cypher_query": cypher_normalized,
                "params": params,
            }
        else:
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"%(graph_name)s::text, %(cypher_query)s::text"
                f") AS ({as_clause_str})"
            )
            run_params = {
                "graph_name": validated_graph_name,
                "cypher_query": cypher_normalized,
            }

        # Use hashes for logging to avoid exposing sensitive data
        query_hash = hashlib.sha256(cypher_normalized.encode()).hexdigest()[:8]
        logger.info(
            "execute_cypher: graph=%s, query_hash=%s, len=%d",
            validated_graph_name,
            query_hash,
            len(cypher_normalized),
        )

        try:
            return await self.db_conn.execute_query(
                runnable_sql, run_params, time_limit_seconds=time_limit_seconds, conn=conn
            )
        except Exception as e:
            logger.error(
                "execute_cypher failed: graph=%s, query_hash=%s, error_type=%s",
                validated_graph_name,
                query_hash,
                type(e).__name__,
                exc_info=True,
            )
            raise

    async def stream_cypher(
        self,
        graph_name: str,
        cypher_query: str,
        chunk_size: int,
        cursor_name: str,
        conn: psycopg.AsyncConnection,
        params: Optional[dict] = None,
    ) -> AsyncGenerator[list[dict], None]:
        """Stream Cypher results via a psycopg server-side cursor.

        Yields successive `list[dict]` batches of up to `chunk_size` rows each
        without materialising the full result in Python memory.  The caller is
        responsible for providing an open connection (`conn`) and for
        consuming (or closing) the generator before `conn` is returned to the
        pool.

        Server-side cursors require a transaction to be open; psycopg's default
        autocommit=False satisfies this automatically.
        """
        validated_graph_name = validate_graph_name(graph_name)
        cypher_normalized = cypher_query.rstrip()
        if cypher_normalized.endswith(";"):
            cypher_normalized = cypher_normalized[:-1].rstrip()

        has_params = params is not None
        return_cols = cypher_return_columns(cypher_query)
        as_clause_str = ", ".join(f'"{c}" agtype' for c in return_cols)

        if has_params:
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"%(graph_name)s::text, %(cypher_query)s::text, %(params)s::agtype"
                f") AS ({as_clause_str})"
            )
            run_params: dict = {
                "graph_name": validated_graph_name,
                "cypher_query": cypher_normalized,
                "params": params,
            }
        else:
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"%(graph_name)s::text, %(cypher_query)s::text"
                f") AS ({as_clause_str})"
            )
            run_params = {
                "graph_name": validated_graph_name,
                "cypher_query": cypher_normalized,
            }

        query_hash = hashlib.sha256(cypher_normalized.encode()).hexdigest()[:8]
        logger.info(
            "stream_cypher: graph=%s, query_hash=%s, chunk_size=%d",
            validated_graph_name,
            query_hash,
            chunk_size,
        )

        safe_cursor = _sanitize_cursor_name(cursor_name)
        async with conn.cursor(name=safe_cursor) as cur:
            await cur.execute(runnable_sql, run_params)
            while True:
                rows = await cur.fetchmany(chunk_size)
                if not rows:
                    break
                yield rows  # type: ignore[misc]
