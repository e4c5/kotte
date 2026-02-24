"""Unit tests for database module (DatabaseConnection helpers)."""

import pytest
from unittest.mock import AsyncMock

from app.core.database import DatabaseConnection
from app.core.errors import APIException
from app.core.errors import APIException


class TestCypherReturnColumns:
    """Tests for _cypher_return_columns static method."""

    def test_no_return_returns_result(self):
        """Query without RETURN yields default column ['result']."""
        assert DatabaseConnection._cypher_return_columns("MATCH (n) DELETE n") == ["result"]

    def test_return_single_expression_no_alias(self):
        """Single return expression without AS gets c1."""
        assert DatabaseConnection._cypher_return_columns("MATCH (n) RETURN n") == ["c1"]

    def test_return_with_as_alias(self):
        """Return with AS alias uses the alias name."""
        assert DatabaseConnection._cypher_return_columns(
            "MATCH (n) RETURN n AS node"
        ) == ["node"]

    def test_return_multiple_columns_mixed(self):
        """Multiple columns with and without AS."""
        q = "MATCH (a), (b) RETURN a AS first, b, a.name AS name"
        assert DatabaseConnection._cypher_return_columns(q) == ["first", "c2", "name"]

    def test_return_stops_at_order_by(self):
        """RETURN clause stops at ORDER BY."""
        q = "MATCH (n) RETURN n AS node ORDER BY n.name"
        assert DatabaseConnection._cypher_return_columns(q) == ["node"]

    def test_return_stops_at_limit(self):
        """RETURN clause stops at LIMIT."""
        q = "MATCH (n) RETURN n AS node LIMIT 10"
        assert DatabaseConnection._cypher_return_columns(q) == ["node"]

    def test_return_stops_at_skip(self):
        """RETURN clause stops at SKIP."""
        q = "MATCH (n) RETURN n AS node SKIP 5"
        assert DatabaseConnection._cypher_return_columns(q) == ["node"]

    def test_return_with_trailing_semicolon(self):
        """Trailing semicolon is included in query; parser still finds RETURN."""
        q = "MATCH (n) RETURN n AS x;"
        assert DatabaseConnection._cypher_return_columns(q) == ["x"]

    def test_case_insensitive_return_and_as(self):
        """RETURN and AS matching is case insensitive."""
        assert DatabaseConnection._cypher_return_columns(
            "match (n) return n as Node"
        ) == ["Node"]
        assert DatabaseConnection._cypher_return_columns(
            "MATCH (n) RETURN n AS my_col"
        ) == ["my_col"]

    def test_invalid_alias_fallback_to_cn(self):
        """Alias that is not a valid identifier falls back to cN."""
        # Hyphen or space in "alias" would break; safe identifier only
        q = "MATCH (n) RETURN n AS c1"  # c1 is valid
        assert DatabaseConnection._cypher_return_columns(q) == ["c1"]
        # If we had something like "my-col", the regex would not match \w+ and we get c1
        q2 = "MATCH (n) RETURN 1 AS valid_name"
        assert DatabaseConnection._cypher_return_columns(q2) == ["valid_name"]

    def test_multiline_return(self):
        """RETURN with newlines (DOTALL)."""
        q = "MATCH (n) RETURN\n  n AS a,\n  n.name AS b"
        assert DatabaseConnection._cypher_return_columns(q) == ["a", "b"]

    def test_empty_return_expression_fallback(self):
        """No expression after RETURN (e.g. trailing space only) yields ['result']."""
        q = "MATCH (n) RETURN "
        assert DatabaseConnection._cypher_return_columns(q) == ["result"]

    def test_three_columns_all_named(self):
        """Three columns with AS aliases."""
        q = "RETURN 1 AS one, 2 AS two, 3 AS three"
        assert DatabaseConnection._cypher_return_columns(q) == ["one", "two", "three"]

    def test_underscore_and_numbers_in_alias(self):
        """Alias with underscores and numbers is valid."""
        q = "MATCH (n) RETURN n AS col_1"
        assert DatabaseConnection._cypher_return_columns(q) == ["col_1"]

    def test_map_literal_single_column(self):
        """Commas inside map literal do not split; single return column."""
        q = "RETURN {foo: 1, bar: 2} AS m"
        assert DatabaseConnection._cypher_return_columns(q) == ["m"]

    def test_function_call_single_column(self):
        """Commas inside function args do not split; single return column."""
        q = "RETURN func(a, b) AS x"
        assert DatabaseConnection._cypher_return_columns(q) == ["x"]

    def test_list_literal_single_column(self):
        """Commas inside list literal do not split; single return column."""
        q = "RETURN [1, 2, 3] AS arr"
        assert DatabaseConnection._cypher_return_columns(q) == ["arr"]

    def test_string_literal_single_column(self):
        """Commas inside single-quoted string do not split; single return column."""
        q = "RETURN 'a, b' AS s"
        assert DatabaseConnection._cypher_return_columns(q) == ["s"]

    def test_string_literal_double_quote_single_column(self):
        """Commas inside double-quoted string do not split; single return column."""
        q = 'RETURN "a, b" AS s'
        assert DatabaseConnection._cypher_return_columns(q) == ["s"]

    def test_invalid_identifier_fallback_to_cn(self):
        """AS alias that fails safe-identifier regex falls back to cN."""
        q = "MATCH (n) RETURN n AS my-col"
        assert DatabaseConnection._cypher_return_columns(q) == ["c1"]

    def test_unbalanced_brackets_fallback_to_result(self):
        """Unbalanced parentheses/brackets/braces or unclosed string yields ['result']."""
        assert DatabaseConnection._cypher_return_columns("RETURN (a, b") == ["result"]
        assert DatabaseConnection._cypher_return_columns("RETURN a) AS x") == ["result"]
        assert DatabaseConnection._cypher_return_columns("RETURN 'unclosed AS s") == ["result"]


class TestExecuteCypher:
    """Tests for execute_cypher (SQL generation and execute_query call)."""

    def _query_string(self, call_args):
        """Render first arg (query) to string; supports psycopg.sql.Composed."""
        query = call_args[0][0]
        if hasattr(query, "as_string"):
            return query.as_string()
        return str(query)

    @pytest.mark.asyncio
    async def test_execute_cypher_two_arg_form_no_params(self):
        """With params=None, uses 2-arg cypher(...) with graph and cypher as literals."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        await conn.execute_cypher("my_graph", "MATCH (n) RETURN n AS node")
        conn.execute_query.assert_called_once()
        sql_str = self._query_string(conn.execute_query.call_args)
        params = conn.execute_query.call_args[0][1]
        assert "ag_catalog.cypher(" in sql_str
        assert "my_graph" in sql_str
        assert "MATCH (n) RETURN n AS node" in sql_str
        assert params is None

    @pytest.mark.asyncio
    async def test_execute_cypher_three_arg_form_with_params(self):
        """With params set, uses 3-arg cypher(..., params) with literals in SQL."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        await conn.execute_cypher(
            "g", "RETURN n AS x", params={"n": 1}
        )
        conn.execute_query.assert_called_once()
        sql_str = self._query_string(conn.execute_query.call_args)
        params = conn.execute_query.call_args[0][1]
        assert "ag_catalog.cypher(" in sql_str
        assert "'g'" in sql_str or "g" in sql_str
        assert "RETURN n AS x" in sql_str
        assert '{"n": 1}' in sql_str
        assert "::agtype" in sql_str
        assert params is None

    @pytest.mark.asyncio
    async def test_execute_cypher_strips_trailing_semicolon(self):
        """Trailing semicolon in cypher is stripped before embedding in SQL."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        await conn.execute_cypher("g", "RETURN 1 AS x;")
        sql_str = self._query_string(conn.execute_query.call_args)
        assert "RETURN 1 AS x" in sql_str
        assert "RETURN 1 AS x;" not in sql_str

    @pytest.mark.asyncio
    async def test_execute_cypher_invalid_graph_name_raises(self):
        """Invalid graph name (e.g. contains quote) raises APIException."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        with pytest.raises(APIException):
            await conn.execute_cypher("my'graph", "RETURN 1 AS c1")
        conn.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_cypher_returns_result_from_execute_query(self):
        """Return value is that of execute_query."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        expected = [{"node": "value"}]
        conn.execute_query = AsyncMock(return_value=expected)
        result = await conn.execute_cypher("g", "RETURN n AS node")
        assert result == expected
