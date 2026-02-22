"""Graph metadata endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory
from app.core.validation import validate_graph_name, validate_label_name
from app.models.graph import (
    GraphInfo,
    GraphMetadata,
    MetaGraphResponse,
    NodeLabel,
    EdgeLabel,
    MetaGraphEdge,
    NodeExpandRequest,
    NodeExpandResponse,
    NodeDeleteRequest,
    NodeDeleteResponse,
)
from app.services.metadata import MetadataService
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db_connection(session: dict = Depends(get_session)) -> DatabaseConnection:
    """Get database connection from session."""
    db_conn = session.get("db_connection")
    if not db_conn:
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message="Database connection not established",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
        )
    return db_conn


@router.get("", response_model=list[GraphInfo])
async def list_graphs(
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> list[GraphInfo]:
    """List all available AGE graphs in the database."""
    try:
        # Query AGE catalog for graphs
        query = """
            SELECT name, graphid
            FROM ag_catalog.ag_graph
            ORDER BY name
        """
        rows = await db_conn.execute_query(query)

        return [
            GraphInfo(name=row["name"], id=str(row["graphid"]))
            for row in rows
        ]
    except Exception as e:
        logger.exception("Error listing graphs")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to list graphs: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e


@router.get("/{graph_name}/metadata", response_model=GraphMetadata)
async def get_graph_metadata(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> GraphMetadata:
    """Get metadata for a specific graph."""
    try:
        # Validate graph name format (prevents SQL injection)
        validated_graph_name = validate_graph_name(graph_name)
        
        # Verify graph exists (using parameterized query)
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": validated_graph_name}
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{validated_graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )

        # Get node labels with counts
        node_query = """
            SELECT DISTINCT label.name as label_name
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'v'
            ORDER BY label_name
        """
        node_label_rows = await db_conn.execute_query(
            node_query, {"graph_name": validated_graph_name}
        )

        node_labels = []
        for row in node_label_rows:
            label_name = row["label_name"]
            # Validate label name
            validated_label_name = validate_label_name(label_name)
            
            # Get count: AGE stores each label in schema (graph name) with table name = label name
            count_query = """
                SELECT c.reltuples::bigint as estimate
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %(schema_name)s AND c.relname = %(rel_name)s
            """
            count = await db_conn.execute_scalar(
                count_query,
                {"schema_name": validated_graph_name, "rel_name": validated_label_name},
            ) or 0
            if count == 0:
                count = await MetadataService.get_exact_counts(
                    db_conn, validated_graph_name, validated_label_name, "v"
                )

            # Discover properties by sampling
            properties = await MetadataService.discover_properties(
                db_conn, validated_graph_name, validated_label_name, "v"
            )

            node_labels.append(
                NodeLabel(label=label_name, count=int(count), properties=properties)
            )

        # Get edge labels with counts
        edge_query = """
            SELECT DISTINCT label.name as label_name
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            ORDER BY label_name
        """
        edge_label_rows = await db_conn.execute_query(
            edge_query, {"graph_name": validated_graph_name}
        )

        edge_labels = []
        for row in edge_label_rows:
            label_name = row["label_name"]
            # Validate label name
            validated_label_name = validate_label_name(label_name)
            
            # Get count: AGE stores each label in schema (graph name) with table name = label name
            count_query = """
                SELECT c.reltuples::bigint as estimate
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %(schema_name)s AND c.relname = %(rel_name)s
            """
            count = await db_conn.execute_scalar(
                count_query,
                {"schema_name": validated_graph_name, "rel_name": validated_label_name},
            ) or 0
            if count == 0:
                count = await MetadataService.get_exact_counts(
                    db_conn, validated_graph_name, validated_label_name, "e"
                )

            # Discover properties by sampling
            properties = await MetadataService.discover_properties(
                db_conn, validated_graph_name, validated_label_name, "e"
            )

            # Calculate property statistics for numeric properties
            from app.models.graph import PropertyStatistics
            property_stats = []
            for prop in properties:
                stats = await MetadataService.get_property_statistics(
                    db_conn, validated_graph_name, validated_label_name, "e", prop
                )
                if stats["min"] is not None and stats["max"] is not None:
                    property_stats.append(
                        PropertyStatistics(
                            property=prop, min=stats["min"], max=stats["max"]
                        )
                    )

            edge_labels.append(
                EdgeLabel(
                    label=label_name,
                    count=int(count),
                    properties=properties,
                    property_statistics=property_stats,
                )
            )

        return GraphMetadata(
            graph_name=validated_graph_name,
            node_labels=node_labels,
            edge_labels=edge_labels,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error getting metadata for graph {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get graph metadata: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e


@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    try:
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": graph_name}
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )

        # Query to discover label-to-label patterns via edges
        # This queries the edge tables to find which node labels connect via which edge labels
        meta_query = f"""
            WITH edge_labels AS (
                SELECT DISTINCT label.name as edge_label
                FROM ag_catalog.ag_label label
                JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            )
            SELECT 
                e.edge_label,
                COUNT(*) as count
            FROM edge_labels e
            CROSS JOIN LATERAL (
                SELECT start_id, end_id
                FROM {graph_name}.{e.edge_label}
                LIMIT 1000
            ) edge_sample
            GROUP BY e.edge_label
        """

        # Simplified approach: query each edge label to find source/target patterns
        # Get all edge labels
        edge_query = """
            SELECT DISTINCT label.name as edge_label
            FROM ag_catalog.ag_label label
            JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
            WHERE graph.name = %(graph_name)s AND label.kind = 'e'
            ORDER BY edge_label
        """
        edge_rows = await db_conn.execute_query(edge_query, {"graph_name": validated_graph_name})

        relationships = []
        for edge_row in edge_rows:
            edge_label = edge_row["edge_label"]
            try:
                # Validate edge label name
                validated_edge_label = validate_label_name(edge_label)
                
                # Sample edges to discover source/target label patterns
                # Use validated names (already validated for SQL injection)
                sample_query = f"""
                    SELECT 
                        start_id,
                        end_id
                    FROM {validated_graph_name}.{validated_edge_label}
                    LIMIT 100
                """
                samples = await db_conn.execute_query(sample_query)

                # For each sample, find the labels of start and end nodes
                # This is a simplified approach - in production, you'd want to
                # query the vertex tables more efficiently
                for sample in samples[:10]:  # Limit to avoid too many queries
                    start_id = sample.get("start_id")
                    end_id = sample.get("end_id")

                    # Find source label (using validated graph name)
                    source_query = """
                        SELECT label.name as label_name
                        FROM ag_catalog.ag_label label
                        JOIN ag_catalog.ag_graph graph ON label.graph = graph.graphid
                        WHERE graph.name = %(graph_name)s AND label.kind = 'v'
                        LIMIT 1
                    """
                    # Note: This query uses parameterization, but the actual implementation
                    # is simplified and doesn't use this query result
                    # Simplified: we'd need to check which vertex table contains the ID
                    # For now, use a pattern-based approach

                # For simplicity, create a relationship entry
                # In a full implementation, we'd aggregate these properly
                relationships.append(
                    MetaGraphEdge(
                        source_label="*",  # Would be discovered from actual data
                        target_label="*",
                        edge_label=edge_label,
                        count=len(samples),
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to analyze edge label {edge_label}: {e}")
                continue

        validated_graph_name = validate_graph_name(graph_name)
        return MetaGraphResponse(
            graph_name=validated_graph_name,
            relationships=relationships,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error getting meta-graph for {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get meta-graph: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e


@router.post("/{graph_name}/nodes/{node_id}/expand", response_model=NodeExpandResponse)
async def expand_node_neighborhood(
    graph_name: str,
    node_id: str,
    request: NodeExpandRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> NodeExpandResponse:
    """Expand the neighborhood of a node up to a specified depth."""
    try:
        # Validate graph name
        validated_graph_name = validate_graph_name(graph_name)
        
        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(
            graph_check, {"graph_name": validated_graph_name}
        )
        if not graph_id:
            raise APIException(
                code=ErrorCode.GRAPH_NOT_FOUND,
                message=f"Graph '{validated_graph_name}' not found",
                category=ErrorCategory.NOT_FOUND,
                status_code=404,
            )

        # Parse node ID (can be integer or string)
        try:
            node_id_int = int(node_id)
        except ValueError:
            raise APIException(
                code=ErrorCode.QUERY_VALIDATION_ERROR,
                message=f"Invalid node ID format: '{node_id}'. Must be a number.",
                category=ErrorCategory.VALIDATION,
                status_code=422,
            )

        # Build Cypher query for neighborhood expansion
        # MATCH path = (n)-[*1..depth]-(m) WHERE id(n) = $node_id
        # Return all nodes and edges in the path
        depth = request.depth
        limit = request.limit
        
        # Use variable-length path matching
        # Note: AGE uses id() function to get node ID
        # We'll return the path and extract nodes/edges from it
        cypher_query = f"""
            MATCH path = (n)-[*1..{depth}]-(m)
            WHERE id(n) = $node_id
            WITH DISTINCT path, m
            LIMIT $limit
            UNWIND relationships(path) as rel
            RETURN DISTINCT m, rel
        """
        
        # Execute via execute_cypher (literal SQL) to avoid cypher() overload issues
        params = {
            "node_id": node_id_int,
            "limit": limit,
        }
        raw_rows = await db_conn.execute_cypher(
            validated_graph_name, cypher_query, params=params
        )
        
        # Parse results and extract nodes/edges
        all_nodes = {}
        all_edges = []
        edge_ids = set()
        
        for raw_row in raw_rows:
            for col_name, agtype_value in raw_row.items():
                parsed_value = AgTypeParser.parse(agtype_value)
                
                if isinstance(parsed_value, dict):
                    # Could be a node or a list of relationships
                    if parsed_value.get("type") == "node":
                        node_id = parsed_value.get("id")
                        if node_id:
                            all_nodes[str(node_id)] = parsed_value
                    elif parsed_value.get("type") == "edge":
                        edge_id = parsed_value.get("id")
                        if edge_id and edge_id not in edge_ids:
                            all_edges.append(parsed_value)
                            edge_ids.add(edge_id)
                elif isinstance(parsed_value, list):
                    # Could be a list of relationships
                    for item in parsed_value:
                        if isinstance(item, dict):
                            if item.get("type") == "edge":
                                edge_id = item.get("id")
                                if edge_id and edge_id not in edge_ids:
                                    all_edges.append(item)
                                    edge_ids.add(edge_id)
                            elif item.get("type") == "node":
                                node_id = item.get("id")
                                if node_id:
                                    all_nodes[str(node_id)] = item
        
        # Convert nodes dict to list
        nodes_list = list(all_nodes.values())
        
        return NodeExpandResponse(
            nodes=nodes_list,
            edges=all_edges,
            node_count=len(nodes_list),
            edge_count=len(all_edges),
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error expanding neighborhood for node {node_id} in graph {graph_name}")
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to expand node neighborhood: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
        ) from e

