"""Input validation utilities."""

import re
from typing import Optional

from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

# Graph and label names must be valid PostgreSQL identifiers
# Allowed: letters, numbers, underscores, must start with letter or underscore
GRAPH_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
LABEL_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maximum lengths
MAX_GRAPH_NAME_LENGTH = 63  # PostgreSQL identifier limit
MAX_LABEL_NAME_LENGTH = 63
MAX_QUERY_LENGTH = 1000000  # 1MB query limit


def validate_graph_name(graph_name: str) -> str:
    """
    Validate graph name format.

    Args:
        graph_name: Graph name to validate

    Returns:
        Validated graph name

    Raises:
        APIException: If graph name is invalid
    """
    if not graph_name:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message="Graph name cannot be empty",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(graph_name) > MAX_GRAPH_NAME_LENGTH:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=f"Graph name exceeds maximum length of {MAX_GRAPH_NAME_LENGTH}",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not GRAPH_NAME_PATTERN.match(graph_name):
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message="Graph name must contain only letters, numbers, and underscores, and start with a letter or underscore",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return graph_name


def validate_label_name(label_name: str) -> str:
    """
    Validate label name format.

    Args:
        label_name: Label name to validate

    Returns:
        Validated label name

    Raises:
        APIException: If label name is invalid
    """
    if not label_name:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message="Label name cannot be empty",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(label_name) > MAX_LABEL_NAME_LENGTH:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=f"Label name exceeds maximum length of {MAX_LABEL_NAME_LENGTH}",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not LABEL_NAME_PATTERN.match(label_name):
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message="Label name must contain only letters, numbers, and underscores, and start with a letter or underscore",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return label_name


def validate_query_length(cypher_query: str) -> str:
    """
    Validate Cypher query length.

    Args:
        cypher_query: Cypher query to validate

    Returns:
        Validated query

    Raises:
        APIException: If query is too long
    """
    if len(cypher_query) > MAX_QUERY_LENGTH:
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    return cypher_query


def add_visualization_limit(cypher: str, max_limit: int) -> str:
    """
    Add LIMIT to Cypher query if not present (for visualization to cap result size).

    Args:
        cypher: Cypher query string
        max_limit: Maximum number of rows to return

    Returns:
        Cypher with LIMIT appended if absent, otherwise unchanged
    """
    query_with_limit, _ = add_result_limit_if_missing(cypher, max_limit)
    return query_with_limit


def add_result_limit_if_missing(cypher: str, max_limit: int) -> tuple[str, bool]:
    """
    Add LIMIT to a Cypher query if absent.

    Returns:
        (cypher_query, limit_was_added)
    """
    if "LIMIT" in cypher.upper():
        return cypher, False
    return f"{cypher.rstrip()} LIMIT {max_limit}", True


def validate_variable_length_traversal(
    cypher_query: str, max_variable_hops: int
) -> str:
    """
    Validate variable-length traversals to avoid unbounded/high-cost queries.

    Rules:
    - Reject unbounded patterns: [*], [*1..], [*..]
    - Reject upper bounds greater than max_variable_hops: [*1..999]
    """
    pattern = re.compile(r"\[\s*\*\s*(?:(\d+)?\s*\.\.\s*(\d+)?)?\s*\]")
    for match in pattern.finditer(cypher_query):
        token = match.group(0)
        lower_bound = match.group(1)
        upper_bound = match.group(2)
        has_range = ".." in token

        if not has_range:
            # [*] is unbounded
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=(
                    f"Unbounded variable-length traversal '{token}' is not allowed. "
                    f"Use an explicit upper bound like [*1..{max_variable_hops}]."
                ),
                category=ErrorCategory.VALIDATION,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if upper_bound is None:
            # [*1..] or [*..] is unbounded
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=(
                    f"Unbounded variable-length traversal '{token}' is not allowed. "
                    f"Use an explicit upper bound <= {max_variable_hops}."
                ),
                category=ErrorCategory.VALIDATION,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        upper = int(upper_bound)
        if upper > max_variable_hops:
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=(
                    f"Variable-length traversal '{token}' exceeds maximum allowed depth "
                    f"of {max_variable_hops}."
                ),
                category=ErrorCategory.VALIDATION,
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    return cypher_query


def escape_string_literal(value: str) -> str:
    """
    Escape a value for safe use as a SQL string literal (single-quoted).
    Use for DDL function args (create_graph, create_label, etc.) which expect text.
    Must be used after validation (e.g. validate_graph_name, validate_label_name).
    """
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def escape_identifier(identifier: str) -> str:
    """
    Escape PostgreSQL identifier for safe use in SQL.

    This should only be used after validation. PostgreSQL identifiers
    can be quoted with double quotes, but we prefer validation + direct use.

    Args:
        identifier: Identifier to escape

    Returns:
        Escaped identifier (quoted)
    """
    # Replace double quotes with double double quotes
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'
