"""Error handling and structured error responses."""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class ErrorCode:
    """Stable error codes for API responses."""

    # Authentication/Session
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_SESSION = "AUTH_INVALID_SESSION"
    AUTH_SESSION_EXPIRED = "AUTH_SESSION_EXPIRED"

    # Connection/Database
    DB_CONNECT_FAILED = "DB_CONNECT_FAILED"
    DB_UNAVAILABLE = "DB_UNAVAILABLE"
    GRAPH_NOT_FOUND = "GRAPH_NOT_FOUND"
    GRAPH_CONTEXT_INVALID = "GRAPH_CONTEXT_INVALID"

    # Query Execution
    QUERY_VALIDATION_ERROR = "QUERY_VALIDATION_ERROR"
    QUERY_SYNTAX_ERROR = "QUERY_SYNTAX_ERROR"
    QUERY_EXECUTION_ERROR = "QUERY_EXECUTION_ERROR"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    QUERY_CANCELLED = "QUERY_CANCELLED"

    # Import
    IMPORT_INVALID_FILE = "IMPORT_INVALID_FILE"
    IMPORT_VALIDATION_ERROR = "IMPORT_VALIDATION_ERROR"
    IMPORT_JOB_NOT_FOUND = "IMPORT_JOB_NOT_FOUND"
    IMPORT_FAILED = "IMPORT_FAILED"

    # Graph-specific
    NODE_NOT_FOUND = "NODE_NOT_FOUND"
    EDGE_NOT_FOUND = "EDGE_NOT_FOUND"
    GRAPH_CONSTRAINT_VIOLATION = "GRAPH_CONSTRAINT_VIOLATION"
    CYPHER_SYNTAX_ERROR = "CYPHER_SYNTAX_ERROR"

    # System
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorCategory:
    """Error categories for classification."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate_limit"
    INTERNAL = "internal"
    UPSTREAM = "upstream"


class APIError(BaseModel):
    """Structured error response model."""

    code: str
    category: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: str
    timestamp: str
    retryable: bool = False


class APIException(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        category: str = ErrorCategory.INTERNAL,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        self.code = code
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable
        super().__init__(message)


class GraphConstraintViolation(APIException):
    """Raised when a graph constraint is violated (unique, foreign key, etc.)."""

    def __init__(
        self,
        constraint_type: str,
        details: str,
        extra_details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=ErrorCode.GRAPH_CONSTRAINT_VIOLATION,
            message=f"{constraint_type} constraint violated: {details}",
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=extra_details or {},
        )


class GraphNodeNotFound(APIException):
    """Raised when a referenced node does not exist."""

    def __init__(self, node_id: str, graph: str):
        super().__init__(
            code=ErrorCode.NODE_NOT_FOUND,
            message=f"Node {node_id} not found in graph '{graph}'",
            category=ErrorCategory.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class GraphEdgeNotFound(APIException):
    """Raised when a referenced edge does not exist."""

    def __init__(self, edge_id: str, graph: str):
        super().__init__(
            code=ErrorCode.EDGE_NOT_FOUND,
            message=f"Edge {edge_id} not found in graph '{graph}'",
            category=ErrorCategory.NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class GraphCypherSyntaxError(APIException):
    """Raised when a Cypher query has syntax errors."""

    def __init__(self, query: str, error_message: str):
        friendly_message = format_cypher_error(error_message, query)
        super().__init__(
            code=ErrorCode.CYPHER_SYNTAX_ERROR,
            message=friendly_message,
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"query": query[:200], "error": error_message},
        )


def format_cypher_error(error: str, query: str = "") -> str:
    """
    Convert PostgreSQL error to user-friendly Cypher error message.

    Args:
        error: Raw PostgreSQL error message
        query: Cypher query (optional, for line context)

    Returns:
        User-friendly error message
    """
    user_message = error

    patterns = [
        (r"syntax error at or near", "Syntax error near"),
        (r"column .* does not exist", "Property or column does not exist"),
        (r"relation .* does not exist", "Label or relation does not exist"),
    ]
    for pattern, replacement in patterns:
        user_message = re.sub(pattern, replacement, user_message, flags=re.IGNORECASE)

    # Extract line number and add context
    line_match = re.search(r"[Ll]ine (\d+):", error)
    if line_match and query:
        line_num = int(line_match.group(1))
        query_lines = query.split("\n")
        if 1 <= line_num <= len(query_lines):
            user_message += f"\nAt: {query_lines[line_num - 1].strip()}"

    return user_message


def translate_db_error(
    e: Exception,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[APIException]:
    """
    Translate a database exception to an appropriate APIException.

    Catches psycopg constraint violations and returns GraphConstraintViolation.
    Returns None if the exception is not a known DB error (caller should handle).
    context: Optional dict with graph, query, params for structured error details.
    """
    try:
        import psycopg.errors as pg_errors

        if isinstance(e, pg_errors.UniqueViolation):
            return GraphConstraintViolation("unique", str(e), extra_details=context)
        if isinstance(e, pg_errors.ForeignKeyViolation):
            return GraphConstraintViolation(
                "referential integrity", str(e), extra_details=context
            )
        if isinstance(e, pg_errors.NotNullViolation):
            return GraphConstraintViolation("not null", str(e), extra_details=context)
        if isinstance(e, pg_errors.CheckViolation):
            return GraphConstraintViolation("check", str(e), extra_details=context)
    except ImportError:
        pass

    return None


def create_error_response(
    request: Request,
    code: str,
    message: str,
    category: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
    retryable: bool = False,
) -> JSONResponse:
    """Create a structured error response."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    error = APIError(
        code=code,
        category=category,
        message=message,
        details=details,
        request_id=request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        retryable=retryable,
    )

    logger.error(
        f"API Error: {code} - {message}",
        extra={
            "error_code": code,
            "error_category": category,
            "request_id": request_id,
            "status_code": status_code,
            "details": details,
        },
    )

    # Record error metrics
    metrics.record_error(code, category)

    return JSONResponse(
        status_code=status_code,
        content={"error": error.model_dump()},
    )


async def error_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handle APIException instances."""
    return create_error_response(
        request=request,
        code=exc.code,
        message=exc.message,
        category=exc.category,
        status_code=exc.status_code,
        details=exc.details,
        retryable=exc.retryable,
    )


async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.exception("Unhandled exception", exc_info=exc)
    message = "An internal error occurred"
    details: Optional[Dict[str, Any]] = None
    if settings.environment == "development":
        message = str(exc) or message
        details = {"exception_type": type(exc).__name__, "detail": str(exc)}
    return create_error_response(
        request=request,
        code=ErrorCode.INTERNAL_ERROR,
        message=message,
        category=ErrorCategory.INTERNAL,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=False,
        details=details,
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Register error handlers with FastAPI app."""
    app.add_exception_handler(APIException, error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

