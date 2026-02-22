"""Tests for validation utilities."""

import pytest

from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import (
    add_result_limit_if_missing,
    add_visualization_limit,
    escape_identifier,
    validate_graph_name,
    validate_label_name,
    validate_query_length,
    validate_variable_length_traversal,
)


class TestGraphNameValidation:
    """Tests for graph name validation."""

    def test_valid_graph_name(self):
        """Test valid graph names."""
        assert validate_graph_name("my_graph") == "my_graph"
        assert validate_graph_name("graph123") == "graph123"
        assert validate_graph_name("_graph") == "_graph"
        assert validate_graph_name("G") == "G"

    def test_invalid_graph_name_format(self):
        """Test invalid graph name formats."""
        with pytest.raises(APIException) as exc_info:
            validate_graph_name("123graph")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.category == ErrorCategory.VALIDATION
        assert exc_info.value.status_code == 400  # Changed from 422 to 400

        with pytest.raises(APIException) as exc_info:
            validate_graph_name("my-graph")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR

        with pytest.raises(APIException) as exc_info:
            validate_graph_name("my graph")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR

        with pytest.raises(APIException) as exc_info:
            validate_graph_name("")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR

    def test_graph_name_too_long(self):
        """Test graph name exceeding maximum length."""
        long_name = "a" * 64  # 64 characters, exceeds 63 limit
        with pytest.raises(APIException) as exc_info:
            validate_graph_name(long_name)
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.category == ErrorCategory.VALIDATION
        assert exc_info.value.status_code == 400  # Changed from 422 to 400
        assert "exceeds maximum length" in exc_info.value.message


class TestLabelNameValidation:
    """Tests for label name validation."""

    def test_valid_label_name(self):
        """Test valid label names."""
        assert validate_label_name("Person") == "Person"
        assert validate_label_name("person_123") == "person_123"
        assert validate_label_name("_label") == "_label"

    def test_invalid_label_name_format(self):
        """Test invalid label name formats."""
        with pytest.raises(APIException) as exc_info:
            validate_label_name("123label")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR

        with pytest.raises(APIException) as exc_info:
            validate_label_name("my-label")
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR


class TestQueryLengthValidation:
    """Tests for query length validation."""

    def test_valid_query_length(self):
        """Test queries within length limit."""
        small_query = "MATCH (n) RETURN n"
        validate_query_length(small_query)

        # MAX_QUERY_LENGTH - 1 byte should be valid
        # MAX_QUERY_LENGTH is 1000000 (1MB)
        large_query = "a" * (1000000 - 1)
        validate_query_length(large_query)

    def test_query_too_long(self):
        """Test query exceeding maximum length."""
        # MAX_QUERY_LENGTH + 1 byte should be invalid
        # MAX_QUERY_LENGTH is 1000000 (1MB)
        huge_query = "a" * (1000000 + 1)
        with pytest.raises(APIException) as exc_info:
            validate_query_length(huge_query)
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.category == ErrorCategory.VALIDATION
        assert exc_info.value.status_code == 413
        assert "exceeds maximum length" in exc_info.value.message


class TestAddVisualizationLimit:
    """Tests for add_visualization_limit."""

    def test_adds_limit_when_absent(self):
        """LIMIT is appended when not present."""
        result = add_visualization_limit("MATCH (n) RETURN n", 5000)
        assert result.endswith(" LIMIT 5000")
        assert "MATCH (n) RETURN n" in result

    def test_preserves_existing_limit(self):
        """Query with LIMIT is unchanged."""
        cypher = "MATCH (n) RETURN n LIMIT 10"
        result = add_visualization_limit(cypher, 5000)
        assert result == cypher
        assert "LIMIT 5000" not in result

    def test_limit_case_insensitive(self):
        """LIMIT in any case is detected."""
        result = add_visualization_limit("MATCH (n) RETURN n limit 5", 5000)
        assert result == "MATCH (n) RETURN n limit 5"
        result2 = add_visualization_limit("MATCH (n) RETURN n Limit 5", 5000)
        assert result2 == "MATCH (n) RETURN n Limit 5"


class TestAddResultLimitIfMissing:
    """Tests for add_result_limit_if_missing."""

    def test_adds_limit_and_reports_applied(self):
        query, applied = add_result_limit_if_missing("MATCH (n) RETURN n", 100)
        assert applied is True
        assert query.endswith(" LIMIT 100")

    def test_preserves_existing_limit_and_reports_not_applied(self):
        original = "MATCH (n) RETURN n LIMIT 10"
        query, applied = add_result_limit_if_missing(original, 100)
        assert applied is False
        assert query == original


class TestVariableLengthTraversalValidation:
    """Tests for variable-length traversal guardrails."""

    def test_allows_bounded_traversal_within_max(self):
        validate_variable_length_traversal(
            "MATCH p=(a)-[*1..5]->(b) RETURN p", max_variable_hops=20
        )

    def test_rejects_unbounded_star(self):
        with pytest.raises(APIException) as exc_info:
            validate_variable_length_traversal(
                "MATCH p=(a)-[*]->(b) RETURN p", max_variable_hops=20
            )
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.status_code == 422

    def test_rejects_unbounded_range(self):
        with pytest.raises(APIException) as exc_info:
            validate_variable_length_traversal(
                "MATCH p=(a)-[*1..]->(b) RETURN p", max_variable_hops=20
            )
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.status_code == 422

    def test_rejects_excessive_hops(self):
        with pytest.raises(APIException) as exc_info:
            validate_variable_length_traversal(
                "MATCH p=(a)-[*1..50]->(b) RETURN p", max_variable_hops=20
            )
        assert exc_info.value.code == ErrorCode.QUERY_VALIDATION_ERROR
        assert exc_info.value.status_code == 422


class TestEscapeIdentifier:
    """Tests for PostgreSQL identifier escaping."""

    def test_escape_identifier_basic(self):
        """Basic identifiers are wrapped in double quotes."""
        assert escape_identifier("my_graph") == '"my_graph"'
        assert escape_identifier("Person") == '"Person"'

    def test_escape_identifier_with_quotes(self):
        """Internal double quotes are doubled."""
        assert escape_identifier('my"graph') == '"my""graph"'
        assert escape_identifier('my""graph') == '"my""""graph"'

    def test_escape_identifier_malicious_input(self):
        """Malicious-looking input is treated as a single identifier when escaped."""
        malicious = 'test; DROP TABLE users; --'
        escaped = escape_identifier(malicious)
        # Should be a single quoted identifier; no characters removed
        assert escaped == '"test; DROP TABLE users; --"'


