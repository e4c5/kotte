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
    for_visualization: bool = Field(
        default=False,
        description="If true, LIMIT is added to Cypher when absent to cap result size",
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
    graph_elements: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        default=None,
        description="Extracted graph elements (nodes, edges) for visualization",
    )
    visualization_warning: Optional[str] = Field(
        default=None,
        description="Warning message if result exceeds visualization limits",
    )


class QueryCancelRequest(BaseModel):
    """Request to cancel a query."""

    reason: Optional[str] = Field(default=None, description="Cancellation reason")


class QueryCancelResponse(BaseModel):
    """Response from query cancellation."""

    cancelled: bool
    request_id: str


class QueryStreamRequest(BaseModel):
    """Request to stream query results."""

    graph: str = Field(..., description="Graph name")
    cypher: str = Field(..., description="Cypher query string")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="Query parameters"
    )
    chunk_size: int = Field(
        default=1000, ge=1, le=10000, description="Number of rows per chunk"
    )
    offset: int = Field(
        default=0, ge=0, description="Offset for pagination"
    )


class QueryStreamChunk(BaseModel):
    """A chunk of query results."""

    columns: List[str] = Field(..., description="Column names")
    rows: List[QueryResultRow] = Field(..., description="Result rows in this chunk")
    chunk_size: int = Field(..., description="Number of rows in this chunk")
    offset: int = Field(..., description="Offset of this chunk")
    has_more: bool = Field(..., description="Whether more rows are available")
    total_rows: Optional[int] = Field(
        default=None, description="Total number of rows (if known)"
    )

