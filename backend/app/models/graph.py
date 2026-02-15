"""Graph-related models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GraphInfo(BaseModel):
    """Graph metadata."""

    name: str
    id: Optional[str] = None


class NodeLabel(BaseModel):
    """Node label information."""

    label: str
    count: int
    properties: List[str] = Field(default_factory=list)


class EdgeLabel(BaseModel):
    """Edge label information."""

    label: str
    count: int
    properties: List[str] = Field(default_factory=list)


class GraphMetadata(BaseModel):
    """Complete graph metadata."""

    graph_name: str
    node_labels: List[NodeLabel]
    edge_labels: List[EdgeLabel]
    role: Optional[str] = None


class MetaGraphEdge(BaseModel):
    """Meta-graph relationship pattern."""

    source_label: str
    target_label: str
    edge_label: str
    count: int


class MetaGraphResponse(BaseModel):
    """Meta-graph view of label relationships."""

    graph_name: str
    relationships: List[MetaGraphEdge]


class NodeExpandRequest(BaseModel):
    """Request to expand neighborhood of a node."""

    depth: int = Field(default=1, ge=1, le=5, description="Expansion depth (1-5)")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum nodes to return (1-1000)")


class NodeExpandResponse(BaseModel):
    """Response from node expansion."""

    nodes: List[Dict[str, Any]] = Field(..., description="Expanded nodes")
    edges: List[Dict[str, Any]] = Field(..., description="Expanded edges")
    node_count: int = Field(..., description="Number of nodes returned")
    edge_count: int = Field(..., description="Number of edges returned")

