"""Unit tests for database module (DatabaseConnection helpers)."""

import pytest
from app.core.database import DatabaseConnection


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
