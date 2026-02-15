"""Authentication endpoints."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from app.core.auth import get_session, session_manager
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.models.auth import LoginRequest, LoginResponse, LogoutResponse, UserInfo
from app.services.user import user_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, http_request: Request) -> LoginResponse:
    """
    Authenticate user and create session.

    Logs authentication attempt for audit purposes.
    """
    # Get client IP for audit logging
    client_ip = http_request.client.host if http_request.client else "unknown"

    # Authenticate user
    user = user_service.authenticate(request.username, request.password)
    if not user:
        # Log failed authentication attempt
        logger.warning(
            f"Failed login attempt for username '{request.username}' from IP {client_ip}",
            extra={
                "event": "auth_failed",
                "username": request.username,
                "ip": client_ip,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise APIException(
            code=ErrorCode.AUTH_INVALID_SESSION,
            message="Invalid username or password",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # Create session
    session_id = session_manager.create_session(
        user["user_id"], {"username": user["username"]}
    )

    # Set session cookie and CSRF token
    http_request.session["session_id"] = session_id
    # CSRF token is stored in session manager, also store in cookie session for middleware
    session_data = session_manager.get_session(session_id)
    if session_data:
        http_request.session["csrf_token"] = session_data.get("csrf_token")

    # Log successful authentication
    logger.info(
        f"User '{user['username']}' logged in successfully from IP {client_ip}",
        extra={
            "event": "auth_success",
            "user_id": user["user_id"],
            "username": user["username"],
            "ip": client_ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    return LoginResponse(
        user_id=user["user_id"],
        username=user["username"],
        authenticated=True,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    http_request: Request, session: dict = Depends(get_session)
) -> LogoutResponse:
    """
    Logout user and invalidate session.

    Logs logout event for audit purposes.
    """
    session_id = http_request.session.get("session_id")
    user_id = session.get("user_id")
    username = session.get("connection_config", {}).get("username", "unknown")

    # Delete session
    if session_id:
        session_manager.delete_session(session_id)

    # Clear session cookie
    http_request.session.clear()

    # Log logout
    logger.info(
        f"User '{username}' (ID: {user_id}) logged out",
        extra={
            "event": "auth_logout",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    return LogoutResponse(logged_out=True)


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    session: dict = Depends(get_session),
) -> UserInfo:
    """Get current authenticated user information."""
    user_id = session.get("user_id")
    username = session.get("connection_config", {}).get("username", "unknown")

    user = user_service.get_user(user_id)
    if not user:
        raise APIException(
            code=ErrorCode.AUTH_INVALID_SESSION,
            message="User not found",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return UserInfo(user_id=user["user_id"], username=user["username"])


@router.get("/csrf-token")
async def get_csrf_token(
    http_request: Request, session: dict = Depends(get_session)
) -> dict:
    """Get CSRF token for current session."""
    csrf_token = session.get("csrf_token") or http_request.session.get("csrf_token")
    if not csrf_token:
        # Generate and store CSRF token
        import secrets
        csrf_token = secrets.token_urlsafe(32)
        session_id = http_request.session.get("session_id")
        if session_id:
            session_manager.update_session(session_id, {"csrf_token": csrf_token})
            http_request.session["csrf_token"] = csrf_token

    return {"csrf_token": csrf_token}

