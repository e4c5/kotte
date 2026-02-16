"""Error handling and structured error responses."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    return create_error_response(
        request=request,
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred",
        category=ErrorCategory.INTERNAL,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=False,
    )


def setup_error_handlers(app: FastAPI) -> None:
    """Register error handlers with FastAPI app."""
    app.add_exception_handler(APIException, error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

