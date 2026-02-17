"""Authentication models."""

from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Request to authenticate user."""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class LoginResponse(BaseModel):
    """Response after successful login."""

    user_id: str
    username: str
    authenticated: bool = True


class LogoutResponse(BaseModel):
    """Response after logout."""

    logged_out: bool = True


class UserInfo(BaseModel):
    """Current user information."""

    user_id: str
    username: str


