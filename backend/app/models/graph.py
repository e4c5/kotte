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


class PropertyStatistics(BaseModel):
    """Statistics for a numeric property."""

    property: str
    min: Optional[float] = None
    max: Optional[float] = None


class EdgeLabel(BaseModel):
    """Edge label information."""

    label: str
    count: int
    properties: List[str] = Field(default_factory=list)
    property_statistics: List[PropertyStatistics] = Field(
        default_factory=list, description="Statistics for numeric properties (min/max)"
    )


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


class NodeDeleteRequest(BaseModel):
    """Request to delete a node."""

    detach: bool = Field(
        default=False, description="If true, delete node and all its relationships. If false, only delete if no relationships exist."
    )


class NodeDeleteResponse(BaseModel):
    """Response from node deletion."""

    deleted: bool = Field(..., description="Whether the node was deleted")
    node_id: str = Field(..., description="ID of the deleted node")
    edges_deleted: int = Field(default=0, description="Number of edges deleted (if detach=true)")


class ShortestPathRequest(BaseModel):
    """Request to find shortest path between two nodes."""

    source_id: int = Field(..., description="Source node ID")
    target_id: int = Field(..., description="Target node ID")
    max_depth: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum path length in hops (1-20)",
    )


class ShortestPathResponse(BaseModel):
    """Response from shortest path query."""

    path: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Nodes and edges in path order, or None if no path found",
    )
    path_length: int = Field(
        default=0,
        description="Number of edges in the path (0 if no path)",
    )
    nodes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Nodes in path order",
    )
    edges: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Edges in path order",
    )

