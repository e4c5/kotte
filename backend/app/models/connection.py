"""Models for saved database connections."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SavedConnectionRequest(BaseModel):
    """Request to save a connection."""
    name: str = Field(..., description="Connection name", min_length=1, max_length=100)
    host: str = Field(..., description="Database host")
    port: int = Field(..., description="Database port", ge=1, le=65535)
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    sslmode: Optional[str] = Field(None, description="SSL mode")


class SavedConnectionResponse(BaseModel):
    """Response with saved connection metadata (no credentials)."""
    id: str
    name: str
    host: str
    port: int
    database: str
    created_at: str
    updated_at: str


class SavedConnectionDetail(SavedConnectionRequest):
    """Full connection details including credentials (for connection use)."""
    id: str
    created_at: str
    updated_at: str


class SavedConnectionListResponse(BaseModel):
    """List of saved connections."""
    connections: list[SavedConnectionResponse]

