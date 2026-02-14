"""Query execution models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryExecuteRequest(BaseModel):
    """Request to execute a Cypher query."""

    graph: str = Field(..., description="Graph name")
    cypher: str = Field(..., description="Cypher query string")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Query parameters"
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Execution options"
    )


class QueryResultRow(BaseModel):
    """A single row in query result."""

    data: Dict[str, Any] = Field(..., description="Row data")


class QueryExecuteResponse(BaseModel):
    """Response from query execution."""

    columns: List[str] = Field(..., description="Column names")
    rows: List[QueryResultRow] = Field(..., description="Result rows")
    row_count: int = Field(..., description="Number of rows")
    command: Optional[str] = Field(
        default=None, description="PostgreSQL command type"
    )
    stats: Optional[Dict[str, Any]] = Field(
        default=None, description="Query execution statistics"
    )
    request_id: str = Field(..., description="Request ID for cancellation")


class QueryCancelRequest(BaseModel):
    """Request to cancel a query."""

    reason: Optional[str] = Field(default=None, description="Cancellation reason")


class QueryCancelResponse(BaseModel):
    """Response from query cancellation."""

    cancelled: bool
    request_id: str

