"""Graph metadata endpoints."""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import get_session
from app.core.database import DatabaseConnection
from app.core.errors import APIException, ErrorCode, ErrorCategory, translate_db_error
from app.core.validation import validate_graph_name, validate_label_name, escape_identifier
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
    ShortestPathRequest,
    ShortestPathResponse,
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
        api_exc = translate_db_error(e)
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to list graphs: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={"operation": "list_graphs"},
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

            # Get count (using ANALYZE estimates for performance)
            # Use parameterized query with validated names
            table_name = f"{validated_graph_name}_{validated_label_name}"
            count_query = """
                SELECT reltuples::bigint as estimate
                FROM pg_class
                WHERE relname = %(table_name)s
            """
            count = await db_conn.execute_scalar(count_query, {"table_name": table_name}) or 0

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

            # Get count estimate (using parameterized query)
            table_name = f"{validated_graph_name}_{validated_label_name}"
            count_query = """
                SELECT reltuples::bigint as estimate
                FROM pg_class
                WHERE relname = %(table_name)s
            """
            count = await db_conn.execute_scalar(count_query, {"table_name": table_name}) or 0

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
        api_exc = translate_db_error(e, context={"graph": graph_name})
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get graph metadata: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={"graph": graph_name, "operation": "get_graph_metadata"},
        ) from e


@router.get("/{graph_name}/meta-graph", response_model=MetaGraphResponse)
async def get_meta_graph(
    graph_name: str,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    try:
        # Validate graph name format (prevents SQL injection)
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

        # Single Cypher query to discover label-to-label patterns (optimized: 1 query vs 3N+1)
        meta_cypher = """
            MATCH (src)-[rel]->(dst)
            WITH labels(src)[0] as src_label,
                 type(rel) as rel_type,
                 labels(dst)[0] as dst_label
            RETURN src_label, rel_type, dst_label, COUNT(*) as edge_count
            ORDER BY edge_count DESC
            LIMIT 1000
        """
        sql_query = """
            SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text)
            AS (src_label agtype, rel_type agtype, dst_label agtype, edge_count agtype)
        """
        try:
            raw_rows = await db_conn.execute_query(
                sql_query,
                {"graph_name": validated_graph_name, "cypher": meta_cypher.strip()},
            )
        except Exception as e:
            logger.warning(
                "Meta-graph Cypher query failed, falling back to empty: %s", e
            )
            raw_rows = []

        relationships = []
        for row in raw_rows:
            src_label = AgTypeParser.parse(row.get("src_label"))
            rel_type = AgTypeParser.parse(row.get("rel_type"))
            dst_label = AgTypeParser.parse(row.get("dst_label"))
            count = AgTypeParser.parse(row.get("edge_count"))
            relationships.append(
                MetaGraphEdge(
                    source_label=str(src_label) if src_label is not None else "*",
                    target_label=str(dst_label) if dst_label is not None else "*",
                    edge_label=str(rel_type) if rel_type is not None else "?",
                    count=int(count) if count is not None else 0,
                )
            )

        return MetaGraphResponse(
            graph_name=validated_graph_name,
            relationships=relationships,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error getting meta-graph for {graph_name}")
        api_exc = translate_db_error(e, context={"graph": graph_name})
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to get meta-graph: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={"graph": graph_name, "operation": "get_meta_graph"},
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
        
        # Execute query using AGE cypher (::text and ::agtype for correct overload)
        import json
        params = {
            "node_id": node_id_int,
            "limit": limit,
        }
        params_json = json.dumps(params)
        sql_query = """
            SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text, %(params)s::agtype) AS (result agtype)
        """
        sql_params = {"graph_name": validated_graph_name, "cypher": cypher_query, "params": params_json}
        raw_rows = await db_conn.execute_query(sql_query, sql_params)
        
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
        api_exc = translate_db_error(
            e, context={"graph": graph_name, "node_id": node_id}
        )
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to expand node neighborhood: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={"graph": graph_name, "node_id": node_id, "operation": "expand_node"},
        ) from e


@router.post(
    "/{graph_name}/shortest-path",
    response_model=ShortestPathResponse,
)
async def find_shortest_path(
    graph_name: str,
    request: ShortestPathRequest,
    db_conn: DatabaseConnection = Depends(get_db_connection),
) -> ShortestPathResponse:
    """Find shortest path between two nodes using variable-length path matching."""
    try:
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

        max_depth = request.max_depth
        cypher_query = f"""
            MATCH path = (src)-[*1..{max_depth}]-(dst)
            WHERE id(src) = $source_id AND id(dst) = $target_id
            WITH path, size(relationships(path)) as path_length
            ORDER BY path_length
            LIMIT 1
            RETURN nodes(path) as path_nodes, relationships(path) as path_edges, path_length
        """
        import json

        params = {
            "source_id": request.source_id,
            "target_id": request.target_id,
        }
        params_json = json.dumps(params)
        sql_query = """
            SELECT * FROM ag_catalog.cypher(%(graph_name)s::text, %(cypher)s::text, %(params)s::agtype)
            AS (path_nodes agtype, path_edges agtype, path_length agtype)
        """
        raw_rows = await db_conn.execute_query(
            sql_query,
            {
                "graph_name": validated_graph_name,
                "cypher": cypher_query,
                "params": params_json,
            },
        )

        if not raw_rows:
            return ShortestPathResponse(path_length=0)

        row = raw_rows[0]
        nodes_raw = AgTypeParser.parse(row.get("path_nodes"))
        edges_raw = AgTypeParser.parse(row.get("path_edges"))
        path_length_val = AgTypeParser.parse(row.get("path_length")) or 0
        path_length_int = int(path_length_val) if path_length_val is not None else 0

        nodes_list: list[dict] = []
        edges_list: list[dict] = []

        if isinstance(nodes_raw, list):
            for item in nodes_raw:
                if isinstance(item, dict):
                    nodes_list.append(item)
        if isinstance(edges_raw, list):
            for item in edges_raw:
                if isinstance(item, dict):
                    edges_list.append(item)

        # Interleave nodes and edges in traversal order: n0, e0, n1, e1, ..., n_n
        path_combined: list[dict] | None = None
        if nodes_list or edges_list:
            path_combined = []
            for i in range(len(edges_list)):
                if i < len(nodes_list):
                    path_combined.append(nodes_list[i])
                path_combined.append(edges_list[i])
            if nodes_list:
                path_combined.append(nodes_list[-1])
        return ShortestPathResponse(
            path=path_combined,
            path_length=path_length_int,
            nodes=nodes_list,
            edges=edges_list,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(
            f"Error finding shortest path in graph {graph_name}: {e}"
        )
        api_exc = translate_db_error(
            e,
            context={
                "graph": graph_name,
                "source_id": request.source_id,
                "target_id": request.target_id,
            },
        )
        if api_exc:
            raise api_exc from e
        raise APIException(
            code=ErrorCode.DB_UNAVAILABLE,
            message=f"Failed to find shortest path: {str(e)}",
            category=ErrorCategory.UPSTREAM,
            status_code=500,
            retryable=True,
            details={
                "graph": graph_name,
                "source_id": request.source_id,
                "target_id": request.target_id,
            },
        ) from e

