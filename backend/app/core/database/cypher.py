"""Cypher query execution logic for Apache AGE.

Dynamic SQL is built only from ``validate_graph_name`` output and parameterized
``%(name)s`` placeholders; the RETURN column list is derived from the Cypher text
for the AGE ``AS (...)`` clause, not from arbitrary user-controlled identifiers.
"""

import hashlib
import json
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

    @staticmethod
    def _dollar_quote_cypher(text: str) -> str:
        """Return Cypher wrapped in a safe PostgreSQL dollar-quoted literal."""
        tag = "kotte"
        delim = f"${tag}$"
        while delim in text:
            tag += "_x"
            delim = f"${tag}$"
        return f"{delim}{text}{delim}"

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
        
        # AGE requires AS (col1 agtype, ...) to match RETURN column count and names.
        return_cols = cypher_return_columns(cypher_query)
        as_clause_str = ", ".join(f'"{c}" ag_catalog.agtype' for c in return_cols)

        # Some AGE builds expose only cypher(name, cstring, agtype).
        # Always use 3-arg form and provide '{}' when caller has no params.
        graph_literal = f"'{validated_graph_name}'::name"
        cypher_literal = self._dollar_quote_cypher(cypher_normalized) + "::cstring"
        runnable_sql = (
            f"SELECT * FROM ag_catalog.cypher("
            f"{graph_literal}, {cypher_literal}, %(params)s::ag_catalog.agtype"
            f") AS ({as_clause_str})"
        )
        run_params = {
            "params": json.dumps(params if params is not None else {}),
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
