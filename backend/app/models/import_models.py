"""CSV import models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CSVImportRequest(BaseModel):
    """Request to import CSV files."""

    graph_name: str = Field(..., description="Target graph name")
    node_files: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Node file configurations (label, file, drop_if_exists)",
    )
    edge_files: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Edge file configurations (label, file, drop_if_exists)",
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Import options"
    )


class ImportJobStatus(BaseModel):
    """Import job status."""

    job_id: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    phase: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    created_labels: List[str] = Field(default_factory=list)
    inserted_rows: int = 0
    rejected_rows: int = 0
    errors: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CSVImportResponse(BaseModel):
    """Response from CSV import request."""

    job_id: str
    status: str
    message: str

