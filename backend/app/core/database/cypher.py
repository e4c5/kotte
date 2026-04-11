"""Cypher query execution logic for Apache AGE."""

import json
import logging
from typing import Optional

from app.core.database.utils import dollar_quote_tag, cypher_return_columns
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
        timeout: Optional[int] = None,
    ) -> list[dict]:
        """
        Execute a Cypher query via Apache AGE using literal SQL (graph and query as literals).
        AGE's cypher() does not support bound (text, text) parameters; we pass validated
        literals (dollar-quoted for cypher, escaped for graph name and params).
        When there are no Cypher parameters we use the 2-arg cypher(graph, query) form;
        when params are present we use the 3-arg form with a literal agtype.
        A trailing semicolon is stripped before sending to AGE, which does not expect it.
        """
        validated_graph_name = validate_graph_name(graph_name)
        cypher_normalized = cypher_query.rstrip()
        if cypher_normalized.endswith(";"):
            cypher_normalized = cypher_normalized[:-1].rstrip()
        tag = dollar_quote_tag(cypher_normalized)
        graph_literal = validated_graph_name.replace("'", "''")
        cypher_literal = tag + cypher_normalized + tag
        has_params = bool(params)
        params_json = json.dumps(params) if has_params else "null"

        # AGE requires AS (col1 agtype, ...) to match RETURN column count and names.
        # Use quoted identifiers for column names.
        return_cols = cypher_return_columns(cypher_query)
        as_clause_str = ", ".join(f'"{c}" agtype' for c in return_cols)

        if has_params:
            params_literal = params_json.replace("'", "''")
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"'{graph_literal}', {cypher_literal}, '{params_literal}'::agtype"
                f") AS ({as_clause_str})"
            )
            run_params: Optional[dict] = None
        else:
            runnable_sql = (
                f"SELECT * FROM ag_catalog.cypher("
                f"'{graph_literal}', {cypher_literal}"
                f") AS ({as_clause_str})"
            )
            run_params = None

        logger.info(
            "execute_cypher: graph=%s, user cypher (verbatim): %s",
            validated_graph_name,
            cypher_query,
        )
        logger.info("execute_cypher: generated SQL (template): %s", runnable_sql)

        try:
            return await self.db_conn.execute_query(runnable_sql, run_params, timeout=timeout)
        except Exception:
            logger.error(
                "execute_cypher: query failed; full generated SQL: %s",
                runnable_sql,
                exc_info=True,
            )
            raise
