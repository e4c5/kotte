"""User management endpoints (D1.2).

Admin-only:  POST   /api/v1/users          — create user
Authenticated: PATCH /api/v1/users/me/password — change own password
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.core.auth import get_session
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.models.auth import UserInfo
from app.services import audit
from app.services.user import user_service

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    http_request: Request,
    session: Annotated[dict, Depends(get_session)],
) -> UserInfo:
    """Create a new user. Admin only."""
    actor_id = session.get("user_id")
    if session.get("role") != "admin":
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Admin privileges required",
            category=ErrorCategory.AUTHENTICATION,
            status_code=status.HTTP_403_FORBIDDEN,
        )
    user = await user_service.create_user(body.username, body.password)
    request_id = getattr(http_request.state, "request_id", None)
    audit.fire_and_forget(
        "user_created",
        actor_id=str(actor_id),
        request_id=request_id,
        payload={"username": body.username},
    )
    logger.info("Admin '%s' created user", actor_id)
    return UserInfo(user_id=user["user_id"], username=user["username"])


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    http_request: Request,
    session: Annotated[dict, Depends(get_session)],
) -> None:
    """Change the authenticated user's password."""
    user_id = session.get("user_id")
    request_id = getattr(http_request.state, "request_id", None)
    await user_service.change_password(str(user_id), body.old_password, body.new_password)
    audit.fire_and_forget(
        "password_changed",
        actor_id=str(user_id),
        request_id=request_id,
    )
    logger.info("User '%s' changed password", user_id)
