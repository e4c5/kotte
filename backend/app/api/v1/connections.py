"""Saved database connection endpoints."""

import logging
from typing import List

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response

from app.core.auth import get_session
from app.core.connection_storage import connection_storage
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.models.connection import (
    SavedConnectionRequest,
    SavedConnectionResponse,
    SavedConnectionDetail,
    SavedConnectionListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=SavedConnectionResponse, status_code=status.HTTP_201_CREATED)
async def save_connection(
    request: SavedConnectionRequest,
    session: dict = Depends(get_session),
) -> SavedConnectionResponse:
    """
    Save a database connection (encrypted).
    
    Credentials are encrypted using AES-256-GCM with user-specific key derivation.
    """
    user_id = session.get("user_id")
    if not user_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHORIZATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        connection_id = connection_storage.save_connection(
            user_id=user_id,
            name=request.name,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
            sslmode=request.sslmode,
        )
        
        # Get the saved connection to return metadata
        conn = connection_storage.get_connection(user_id, connection_id)
        if not conn:
            raise APIException(
                code=ErrorCode.INTERNAL_ERROR,
                message="Failed to retrieve saved connection",
                category=ErrorCategory.INTERNAL,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
        logger.info(
            f"User {user_id} saved connection '{request.name}'",
            extra={
                "event": "connection_saved",
                "user_id": user_id,
                "connection_id": connection_id,
                "connection_name": request.name,
            },
        )
        
        return SavedConnectionResponse(
            id=conn["id"],
            name=conn["name"],
            host=conn["host"],
            port=conn["port"],
            database=conn["database"],
            created_at=conn["created_at"],
            updated_at=conn["updated_at"],
        )
    except ValueError as e:
        # Duplicate name or validation error
        raise APIException(
            code=ErrorCode.QUERY_VALIDATION_ERROR,
            message=str(e),
            category=ErrorCategory.VALIDATION,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except Exception as e:
        logger.exception(f"Error saving connection: {e}")
        raise APIException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to save connection",
            category=ErrorCategory.INTERNAL,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e


@router.get("", response_model=list[SavedConnectionResponse])
async def list_connections(
    session: dict = Depends(get_session),
) -> list[SavedConnectionResponse]:
    """List all saved connections for the current user."""
    user_id = session.get("user_id")
    if not user_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHORIZATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        connections = connection_storage.list_connections(user_id)
        return [
            SavedConnectionResponse(
                id=conn["id"],
                name=conn["name"],
                host=conn["host"],
                port=conn["port"],
                database=conn["database"],
                created_at=conn["created_at"],
                updated_at=conn["updated_at"],
            )
            for conn in connections
        ]
    except Exception as e:
        logger.exception(f"Error listing connections: {e}")
        raise APIException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to list connections",
            category=ErrorCategory.INTERNAL,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e


@router.get("/{connection_id}", response_model=SavedConnectionDetail)
async def get_connection(
    connection_id: str,
    session: dict = Depends(get_session),
) -> SavedConnectionDetail:
    """
    Get a saved connection with decrypted credentials.
    
    Use this endpoint to retrieve connection details for connecting.
    Credentials are decrypted server-side and returned in the response.
    """
    user_id = session.get("user_id")
    if not user_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHORIZATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        conn = connection_storage.get_connection(user_id, connection_id)
        if not conn:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,  # Reuse existing code
                message=f"Connection '{connection_id}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
        logger.info(
            f"User {user_id} retrieved connection '{connection_id}'",
            extra={
                "event": "connection_retrieved",
                "user_id": user_id,
                "connection_id": connection_id,
            },
        )
        
        return SavedConnectionDetail(
            id=conn["id"],
            name=conn["name"],
            host=conn["host"],
            port=conn["port"],
            database=conn["database"],
            username=conn["username"],
            password=conn["password"],
            sslmode=conn.get("sslmode"),
            created_at=conn["created_at"],
            updated_at=conn["updated_at"],
        )
    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving connection: {e}")
        raise APIException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to retrieve connection",
            category=ErrorCategory.INTERNAL,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    session: dict = Depends(get_session),
) -> Response:
    """Delete a saved connection."""
    user_id = session.get("user_id")
    if not user_id:
        raise APIException(
            code=ErrorCode.AUTH_REQUIRED,
            message="Authentication required",
            category=ErrorCategory.AUTHORIZATION,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    
    try:
        success = connection_storage.delete_connection(user_id, connection_id)
        if not success:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,  # Reuse existing code
                message=f"Connection '{connection_id}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
        logger.info(
            f"User {user_id} deleted connection '{connection_id}'",
            extra={
                "event": "connection_deleted",
                "user_id": user_id,
                "connection_id": connection_id,
            },
        )
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting connection: {e}")
        raise APIException(
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to delete connection",
            category=ErrorCategory.INTERNAL,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e

