"""User management service."""

import hashlib
import logging
from typing import Optional

from app.core.errors import APIException, ErrorCode, ErrorCategory
from fastapi import status

logger = logging.getLogger(__name__)


class UserService:
    """Service for user authentication and management."""

    # In-memory user store for MVP
    # In production, this would be a database
    _users: dict[str, dict] = {
        "admin": {
            "user_id": "admin",
            "username": "admin",
            "password_hash": hashlib.sha256("admin".encode()).hexdigest(),  # Change in production!
            "active": True,
        }
    }

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
        user = cls._users.get(username)
        if not user:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None

        if not user.get("active", True):
            logger.warning(f"Authentication failed: user '{username}' is inactive")
            return None

        # Simple password hash comparison (use bcrypt/argon2 in production)
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user["password_hash"] != password_hash:
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
        if username in cls._users:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"User '{username}' already exists",
                category=ErrorCategory.CONFLICT,
                status_code=status.HTTP_409_CONFLICT,
            )

        user_id = username
        password_hash = hashlib.sha256(password.encode()).hexdigest()

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


