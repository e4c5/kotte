"""Tests for validation utilities."""

import pytest

from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import (
    validate_graph_name,
    validate_label_name,
    validate_query_length,
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



