"""Cypher query execution logic for Apache AGE.

Dynamic SQL is built only from ``validate_graph_name`` output and parameterized
``%(name)s`` placeholders; the RETURN column list is derived from the Cypher text
for the AGE ``AS (...)`` clause, not from arbitrary user-controlled identifiers.
"""

import hashlib
import logging
from typing import Optional

import psycopg

from app.core.database.utils import cypher_return_columns
from app.core.validation import validate_graph_name

logger = logging.getLogger(__name__)


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
