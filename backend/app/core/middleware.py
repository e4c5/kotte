"""Request middleware."""

import logging
import secrets
import time
import uuid
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to request state and response headers."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Collect HTTP request metrics for Prometheus."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/api/v1/metrics" or request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()
        method = request.method
        # Normalize endpoint path (remove IDs, etc.)
        endpoint = self._normalize_endpoint(request.url.path)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            # Re-raise to let error handler deal with it
            raise
        finally:
            duration = time.time() - start_time
            metrics.record_http_request(method, endpoint, status_code, duration)

        return response

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics (remove IDs, etc.)."""
        # Remove API prefix
        if path.startswith("/api/v1/"):
            path = path[8:]
        elif path.startswith("/api/"):
            path = path[5:]

        # Replace UUIDs and IDs with placeholders
        import re
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        # Replace graph names and node IDs in specific patterns
        path = re.sub(r'/graphs/[^/]+', '/graphs/{graph}', path)
        path = re.sub(r'/nodes/[^/]+', '/nodes/{node_id}', path)

        return path


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware."""

    # Methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        if not settings.csrf_enabled:
            return await call_next(request)

        # Skip CSRF for GET, HEAD, OPTIONS
        if request.method not in self.PROTECTED_METHODS:
            return await call_next(request)

        # Skip CSRF for API docs and login endpoint
        if (
            request.url.path.startswith("/api/docs")
            or request.url.path.startswith("/api/redoc")
            or request.url.path == "/api/v1/auth/login"
        ):
            return await call_next(request)

        # Get CSRF token from header
        csrf_token = request.headers.get("X-CSRF-Token")
        session_csrf = request.session.get("csrf_token")
        
        # Also check session manager if available
        session_id = request.session.get("session_id")
        if not session_csrf and session_id:
            from app.core.auth import session_manager
            session_data = session_manager.get_session(session_id)
            if session_data:
                session_csrf = session_data.get("csrf_token")

        if not csrf_token or csrf_token != session_csrf:
            logger.warning(
                f"CSRF token validation failed for {request.method} {request.url.path}",
                extra={"request_id": getattr(request.state, "request_id", None)},
            )
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="CSRF token validation failed",
                category=ErrorCategory.VALIDATION,
                status_code=status.HTTP_403_FORBIDDEN,
            )

        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""

    def __init__(self, app):
        super().__init__(app)
        # In-memory rate limit store
        # In production, use Redis for distributed rate limiting
        self._ip_requests: dict[str, list[float]] = defaultdict(list)
        self._user_requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60  # Clean up old entries every 60 seconds
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self):
        """Remove old rate limit entries."""
        now = time.time()
        cutoff = now - 60  # Keep last minute

        # Clean IP requests
        for ip in list(self._ip_requests.keys()):
            self._ip_requests[ip] = [
                t for t in self._ip_requests[ip] if t > cutoff
            ]
            if not self._ip_requests[ip]:
                del self._ip_requests[ip]

        # Clean user requests
        for user_id in list(self._user_requests.keys()):
            self._user_requests[user_id] = [
                t for t in self._user_requests[user_id] if t > cutoff
            ]
            if not self._user_requests[user_id]:
                del self._user_requests[user_id]

        self._last_cleanup = now

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Periodic cleanup
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_entries()

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        user_id = request.scope.get("session", {}).get("user_id") if "session" in request.scope else None

        now = time.time()
        cutoff = now - 60  # Last minute

        # Check IP rate limit
        ip_requests = self._ip_requests[client_ip]
        ip_requests = [t for t in ip_requests if t > cutoff]
        self._ip_requests[client_ip] = ip_requests

        if len(ip_requests) >= settings.rate_limit_per_minute:
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}",
                extra={"request_id": getattr(request.state, "request_id", None)},
            )
            raise APIException(
                code=ErrorCode.RATE_LIMITED,
                message="Rate limit exceeded. Please try again later.",
                category=ErrorCategory.RATE_LIMIT,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                retryable=True,
            )

        # Check user rate limit (if authenticated)
        if user_id:
            user_requests = self._user_requests[user_id]
            user_requests = [t for t in user_requests if t > cutoff]
            self._user_requests[user_id] = user_requests

            if len(user_requests) >= settings.rate_limit_per_user:
                logger.warning(
                    f"Rate limit exceeded for user {user_id}",
                    extra={"request_id": getattr(request.state, "request_id", None)},
                )
                raise APIException(
                    code=ErrorCode.RATE_LIMITED,
                    message="Rate limit exceeded. Please try again later.",
                    category=ErrorCategory.RATE_LIMIT,
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    retryable=True,
                )

        # Record request
        self._ip_requests[client_ip].append(now)
        if user_id:
            self._user_requests[user_id].append(now)

        response = await call_next(request)

        # Add rate limit headers
        remaining_ip = settings.rate_limit_per_minute - len(self._ip_requests[client_ip])
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining_ip))
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response

