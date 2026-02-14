"""Session-related models."""

from typing import Optional

from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    """Database connection configuration."""

    host: str = Field(..., description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    sslmode: Optional[str] = Field(
        default=None, description="SSL mode (disable, require, etc.)"
    )


class ConnectRequest(BaseModel):
    """Request to establish database connection."""

    connection: ConnectionConfig


class ConnectResponse(BaseModel):
    """Response after successful connection."""

    session_id: str
    connected: bool
    database: str
    host: str
    port: int
    # Note: credentials are NOT included in response


class DisconnectResponse(BaseModel):
    """Response after disconnection."""

    disconnected: bool


class SessionStatusResponse(BaseModel):
    """Current session status."""

    connected: bool
    database: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    current_graph: Optional[str] = None
    # Note: credentials are NOT included in response

