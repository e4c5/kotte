"""User management service."""

import logging
import os
from typing import Optional

import bcrypt

from app.core.config import settings
from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _build_admin_user() -> dict:
    """Build the default admin user, reading the password from the environment.

    The ``ADMIN_PASSWORD`` environment variable overrides the default password.
    In production, this variable **must** be set to a strong secret.
    """
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
    if admin_password == "admin" and settings.environment == "production":
        logger.warning(
            "Default admin password is in use. "
            "Set the ADMIN_PASSWORD environment variable in production!"
        )
    return {
        "user_id": "admin",
        "username": "admin",
        "password_hash": _hash_password(admin_password),
        "active": True,
    }


class UserService:
    """Service for user authentication and management."""

    # In-memory user store for MVP
    # In production, this would be a database
    _users: dict[str, dict] = {}

    @classmethod
    def _ensure_admin(cls) -> None:
        """Lazily initialise the admin user so tests can override ADMIN_PASSWORD."""
        if "admin" not in cls._users:
            cls._users["admin"] = _build_admin_user()

    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional[dict]:
        """
        Authenticate a user.

        Args:
            username: Username
            password: Plain text password

        Returns:
            User dict if authenticated, None otherwise
        """
        cls._ensure_admin()
        user = cls._users.get(username)
        if not user:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None

        if not user.get("active", True):
            logger.warning(f"Authentication failed: user '{username}' is inactive")
            return None

        if not _verify_password(password, user["password_hash"]):
            logger.warning(f"Authentication failed: invalid password for user '{username}'")
            return None

        logger.info(f"User '{username}' authenticated successfully")
        return {
            "user_id": user["user_id"],
            "username": user["username"],
        }

    @classmethod
    def get_user(cls, user_id: str) -> Optional[dict]:
        """Get user by ID."""
        cls._ensure_admin()
        for user in cls._users.values():
            if user["user_id"] == user_id:
                return {
                    "user_id": user["user_id"],
                    "username": user["username"],
                }
        return None

    @classmethod
    def create_user(cls, username: str, password: str) -> dict:
        """
        Create a new user.

        In production, this would validate password strength, check duplicates, etc.
        """
        cls._ensure_admin()
        if username in cls._users:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"User '{username}' already exists",
                category=ErrorCategory.CONFLICT,
                status_code=status.HTTP_409_CONFLICT,
            )

        user_id = username
        password_hash = _hash_password(password)

        cls._users[username] = {
            "user_id": user_id,
            "username": username,
            "password_hash": password_hash,
            "active": True,
        }

        logger.info(f"Created user '{username}'")
        return {
            "user_id": user_id,
            "username": username,
        }


user_service = UserService()
