"""Health check endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    version: str = "0.1.0"


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str
    timestamp: str
    database: dict
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns 200 if the service is running.
    No authentication required.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check(
    session: dict = Depends(get_session),
) -> ReadinessResponse:
    """
    Readiness check endpoint.
    
    Checks if the service is ready to serve requests:
    - Service is running
    - Database connection is available (if session has one)
    
    Returns 200 if ready, 503 if not ready.
    """
    db_status = {
        "connected": False,
        "status": "not_connected",
    }
    
    # Check if there's a database connection in the session
    db_conn = session.get("db_connection")
    if db_conn:
        try:
            if hasattr(db_conn, "is_connected") and db_conn.is_connected():
                db_status = {
                    "connected": True,
                    "status": "connected",
                }
            elif hasattr(db_conn, "_conn") and db_conn._conn:
                db_status = {
                    "connected": True,
                    "status": "connected",
                }
        except Exception as e:
            logger.warning(f"Error checking database connection: {e}")
            db_status = {
                "connected": False,
                "status": "error",
                "error": str(e),
            }
    
    # Service is ready if it's running (database connection is optional)
    return ReadinessResponse(
        status="ready",
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status,
    )


@router.get("/metrics")
async def metrics_endpoint() -> Response:
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format.
    No authentication required (metrics are typically scraped by Prometheus).
    """
    metrics_data = metrics.get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )

