"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.errors import setup_error_handlers
from app.core.middleware import RequestIDMiddleware

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
        description="Apache AGE Graph Visualizer Backend API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment == "development" else None,
        redoc_url="/api/redoc" if settings.environment == "development" else None,
    )

    # Session middleware (must be before CORS)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        max_age=settings.session_max_age,
        same_site="lax",
        https_only=settings.environment == "production",
    )

    # Request ID middleware
    app.add_middleware(RequestIDMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    setup_error_handlers(app)

    # API routes
    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()

