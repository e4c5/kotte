"""Unit tests for database module (DatabaseConnection helpers)."""

import pytest
from unittest.mock import AsyncMock

from app.core.database import DatabaseConnection
from app.core.errors import APIException


class TestCypherReturnColumns:
    """Tests for cypher RETURN column name inference."""

    def test_no_return_returns_result(self):
        """If no RETURN found, defaults to ['result']."""
        # Accessing protected for testing inference logic
        # pylint: disable=protected-access
        cols = DatabaseConnection._cypher_return_columns("MATCH (n) CREATE (n)")
        assert cols == ["result"]

    def test_return_single_expression_no_alias(self):
        """Single column without AS gets c1."""
        cols = DatabaseConnection._cypher_return_columns("MATCH (n) RETURN n")
        assert cols == ["c1"]

    def test_return_with_as_alias(self):
        """AS alias is extracted correctly."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n AS person")
        assert cols == ["person"]

    def test_return_multiple_columns_mixed(self):
        """Handles multiple columns with and without aliases."""
        cols = DatabaseConnection._cypher_return_columns("RETURN a.name AS name, b, count(*) AS total")
        assert cols == ["name", "c2", "total"]

    def test_return_stops_at_order_by(self):
        """Parsing stops at ORDER BY."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n.id AS id ORDER BY n.id")
        assert cols == ["id"]

    def test_return_stops_at_limit(self):
        """Parsing stops at LIMIT."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n LIMIT 10")
        assert cols == ["c1"]

    def test_return_stops_at_skip(self):
        """Parsing stops at SKIP."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n SKIP 5")
        assert cols == ["c1"]

    def test_return_with_trailing_semicolon(self):
        """Trailing semicolon is ignored."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n AS x;")
        assert cols == ["x"]

    def test_case_insensitive_return_and_as(self):
        """Keywords are case-insensitive."""
        cols = DatabaseConnection._cypher_return_columns("match (n) return n as X")
        assert cols == ["X"]

    def test_invalid_alias_fallback_to_cn(self):
        """Aliases with special chars (not supported by AGE AS clause) fallback to ci."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n AS `my-alias`")
        assert cols == ["c1"]

    def test_multiline_return(self):
        """Handles multiline RETURN clauses."""
        cypher = """
        MATCH (a)-[r]->(b)
        RETURN 
            a.name AS source,
            type(r) AS rel,
            b.name AS target
        """
        cols = DatabaseConnection._cypher_return_columns(cypher)
        assert cols == ["source", "rel", "target"]

    def test_empty_return_expression_fallback(self):
        """Empty return expression defaults to ['result']."""
        cols = DatabaseConnection._cypher_return_columns("RETURN ")
        assert cols == ["result"]

    def test_three_columns_all_named(self):
        """Extraction of three named columns."""
        cols = DatabaseConnection._cypher_return_columns("RETURN a AS x, b AS y, c AS z")
        assert cols == ["x", "y", "z"]

    def test_underscore_and_numbers_in_alias(self):
        """Extracted name can contain underscores and digits."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n AS user_123")
        assert cols == ["user_123"]

    def test_map_literal_single_column(self):
        """Single column returning a map literal."""
        cols = DatabaseConnection._cypher_return_columns("RETURN {a: 1, b: 2}")
        assert cols == ["c1"]

    def test_function_call_single_column(self):
        """Single column returning a function result."""
        cols = DatabaseConnection._cypher_return_columns("RETURN avg(n.age)")
        assert cols == ["c1"]

    def test_list_literal_single_column(self):
        """Single column returning a list literal."""
        cols = DatabaseConnection._cypher_return_columns("RETURN [1, 2, 3]")
        assert cols == ["c1"]

    def test_string_literal_single_column(self):
        """Single column returning a string literal with single quotes."""
        cols = DatabaseConnection._cypher_return_columns("RETURN 'abc, def'")
        assert cols == ["c1"]

    def test_string_literal_double_quote_single_column(self):
        """Single column returning a string literal with double quotes."""
        cols = DatabaseConnection._cypher_return_columns('RETURN "abc, def"')
        assert cols == ["c1"]

    def test_invalid_identifier_fallback_to_cn(self):
        """Alias starting with number is invalid for SQL identifier, fallback to c1."""
        cols = DatabaseConnection._cypher_return_columns("RETURN n AS 123user")
        assert cols == ["c1"]

    def test_unbalanced_brackets_fallback_to_result(self):
        """Complex/malformed return expression fallbacks gracefully."""
        cols = DatabaseConnection._cypher_return_columns("RETURN (n {prop: 1")
        assert cols == ["result"]


class TestExecuteCypher:
    """Tests for DatabaseConnection.execute_cypher helper."""

    def _query_string(self, call_args):
        """Extract query string from AsyncMock call_args."""
        # args[0] is query, args[1] is params
        return call_args[0][0]

    @pytest.mark.asyncio
    async def test_execute_cypher_two_arg_form_no_params(self):
        """With params=None, uses 2-arg cypher(...) with placeholders."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        await conn.execute_cypher("my_graph", "MATCH (n) RETURN n AS node")
        conn.execute_query.assert_called_once()
        sql_str = self._query_string(conn.execute_query.call_args)
        params = conn.execute_query.call_args[0][1]
        assert "ag_catalog.cypher(" in sql_str
        assert "%(graph_name)s" in sql_str
        assert "%(cypher_query)s" in sql_str
        assert params["graph_name"] == "my_graph"
        assert params["cypher_query"] == "MATCH (n) RETURN n AS node"

    @pytest.mark.asyncio
    async def test_execute_cypher_three_arg_form_with_params(self):
        """With params set, uses 3-arg cypher(..., params) with placeholders."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        mock_params = {"n": 1}
        await conn.execute_cypher(
            "g", "RETURN n AS x", params=mock_params
        )
        conn.execute_query.assert_called_once()
        sql_str = self._query_string(conn.execute_query.call_args)
        params = conn.execute_query.call_args[0][1]
        assert "ag_catalog.cypher(" in sql_str
        assert "%(graph_name)s" in sql_str
        assert "%(cypher_query)s" in sql_str
        assert "%(params)s" in sql_str
        assert "::agtype" in sql_str
        assert params["graph_name"] == "g"
        assert params["cypher_query"] == "RETURN n AS x"
        assert params["params"] == mock_params

    @pytest.mark.asyncio
    async def test_execute_cypher_strips_trailing_semicolon(self):
        """Trailing semicolon in cypher is stripped before parameterization."""
        conn = DatabaseConnection(
            host="h", port=5432, database="d", user="u", password="p"
        )
        conn.execute_query = AsyncMock(return_value=[])
        await conn.execute_cypher("g", "RETURN 1 AS x;")
        params = conn.execute_query.call_args[0][1]
        assert params["cypher_query"] == "RETURN 1 AS x"

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
