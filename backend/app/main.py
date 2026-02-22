"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.errors import setup_error_handlers
from app.core.middleware import (
    CSRFMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestIDMiddleware,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Kotte backend...")
    yield
    logger.info("Shutting down Kotte backend...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Kotte API",
        description="""
Apache AGE Graph Visualizer Backend API.

## Features
- **Graphs**: List, metadata, meta-graph, shortest path
- **Queries**: Execute Cypher, templates, streaming
- **Import**: CSV import with transaction support
- **Session**: Auth, database connection, CSRF protection

## Error Codes
- `AUTH_REQUIRED`, `AUTH_INVALID_SESSION`: Authentication
- `GRAPH_NOT_FOUND`, `GRAPH_CONSTRAINT_VIOLATION`: Graph operations
- `CYPHER_SYNTAX_ERROR`, `QUERY_EXECUTION_ERROR`: Query execution
- `DB_UNAVAILABLE`: Database connection
        """.strip(),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment == "development" else None,
        redoc_url="/api/redoc" if settings.environment == "development" else None,
        openapi_tags=[
            {"name": "health", "description": "Health checks and metrics"},
            {"name": "authentication", "description": "Login, logout, session, CSRF token"},
            {"name": "session", "description": "Database connection management"},
            {"name": "connections", "description": "Saved connection storage"},
            {"name": "graphs", "description": "Graph metadata, shortest path, node operations"},
            {"name": "queries", "description": "Cypher execution, templates, streaming"},
            {"name": "import", "description": "CSV import"},
        ],
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # CSRF protection middleware (needs request.session, so Session must run before it)
    if settings.csrf_enabled:
        app.add_middleware(CSRFMiddleware)

    # Rate limiting middleware (runs before CSRF to limit abuse early)
    if settings.rate_limit_enabled:
        app.add_middleware(RateLimitMiddleware)

    # Session middleware (added after CSRF/CORS so it runs before them and populates request.session)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.environment == "production",
        session_cookie=settings.session_cookie_name,
    )

    # Metrics middleware (collect metrics for all requests)
    app.add_middleware(MetricsMiddleware)

    # Request ID middleware (added last so it runs first on requests)
    app.add_middleware(RequestIDMiddleware)

    # Error handlers
    setup_error_handlers(app)

    # API routes
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()

