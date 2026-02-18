"""Session management endpoints."""

import logging

from fastapi import APIRouter, Depends, Request, status
from starlette.responses import JSONResponse

from app.core.auth import get_session, session_manager
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.metrics import metrics
from app.models.session import (
    ConnectRequest,
    ConnectResponse,
    DisconnectResponse,
    SessionStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/connect", response_model=ConnectResponse, status_code=status.HTTP_201_CREATED)
async def connect(
    request: ConnectRequest, http_request: Request, session: dict = Depends(get_session)
) -> ConnectResponse:
    """
    Establish database connection and create session.

    Creates a new session and stores connection configuration server-side.
    Credentials are never returned in the response.
    """
    # Create database connection
    db_conn = DatabaseConnection(
        host=request.connection.host,
        port=request.connection.port,
        database=request.connection.database,
        user=request.connection.user,
        password=request.connection.password,
        sslmode=request.connection.sslmode,
    )

    try:
        await db_conn.connect()
        metrics.record_db_connection_attempt("success")
    except APIException:
        metrics.record_db_connection_attempt("failed")
        raise
    except Exception as e:
        logger.exception("Unexpected error during connection")
        metrics.record_db_connection_attempt("failed")
        metrics.record_error(ErrorCode.DB_CONNECT_FAILED, ErrorCategory.UPSTREAM)
        raise APIException(
            code=ErrorCode.DB_CONNECT_FAILED,
            message=f"Connection failed: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            retryable=True,
        ) from e

    # Get user from authenticated session (required before connection)
    user_id = session.get("user_id")
    session_id = http_request.session.get("session_id")

    # Update session with connection config and store DB connection
    if session_id:
        session_manager.update_session(
            session_id,
            {
                "connection_config": request.connection.model_dump(),
                "db_connection": db_conn,
            },
        )
        # Ensure cookie session has csrf_token so response cookie includes it (CSRF validation)
        if "csrf_token" not in http_request.session and session.get("csrf_token"):
            http_request.session["csrf_token"] = session["csrf_token"]

    # Set session cookie
    http_request.session["session_id"] = session_id

    logger.info(
        f"Session {session_id[:8]}... connected to {request.connection.database}"
    )

    # Record metrics
    metrics.record_session_creation()

    return ConnectResponse(
        session_id=session_id,
        connected=True,
        database=request.connection.database,
        host=request.connection.host,
        port=request.connection.port,
    )


@router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect(
    http_request: Request, session: dict = Depends(get_session)
) -> DisconnectResponse:
    """Disconnect from database and invalidate session."""
    session_id = http_request.session.get("session_id")

    # Close database connection if exists
    db_conn = session.get("db_connection")
    if db_conn:
        try:
            await db_conn.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting database: {e}")

    # Delete session
    if session_id:
        session_manager.delete_session(session_id)
        metrics.record_db_connection_attempt("disconnect")
        metrics.record_session_destruction()

    # Clear session cookie
    http_request.session.clear()

    return DisconnectResponse(disconnected=True)


@router.get("/status", response_model=SessionStatusResponse)
async def get_status(
    http_request: Request, session: dict = Depends(get_session)
) -> SessionStatusResponse:
    """Get current session status."""
    conn_config = session.get("connection_config", {})
    db_conn = session.get("db_connection")

    connected = db_conn is not None

    return SessionStatusResponse(
        connected=connected,
        database=conn_config.get("database") if connected else None,
        host=conn_config.get("host") if connected else None,
        port=conn_config.get("port") if connected else None,
        current_graph=session.get("graph_context"),
    )

