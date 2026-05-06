"""Graph metadata endpoints."""

import asyncio
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.database import DatabaseConnection
from app.core.deps import get_db_connection
from app.core.errors import APIException, ErrorCode, ErrorCategory, translate_db_error
from app.core.validation import validate_graph_name, validate_label_name
from app.models.graph import (
    GraphInfo,
    GraphMetadata,
    MetaGraphResponse,
    NodeLabel,
    EdgeLabel,
    PropertyStatistics,
    MetaGraphEdge,
    NodeExpandRequest,
    NodeExpandResponse,
    ShortestPathRequest,
    ShortestPathResponse,
)
from app.services.metadata import MetadataService
from app.services.agtype import AgTypeParser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_graphs(
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
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

        return [GraphInfo(name=row["name"], id=str(row["graphid"])) for row in rows]
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


@router.get("/{graph_name}/metadata")
async def get_graph_metadata(
    graph_name: str,
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
) -> GraphMetadata:
    """Get metadata for a specific graph."""
    try:
        # Validate graph name format (prevents SQL injection)
        validated_graph_name = validate_graph_name(graph_name)

        # Verify graph exists (using parameterized query)
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
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
        node_count_estimates = await MetadataService.get_label_count_estimates(
            db_conn, validated_graph_name, "v"
        )

        async def build_node_label(row: dict) -> NodeLabel:
            label_name = row["label_name"]
            validated_label_name = validate_label_name(label_name)
            count = int(node_count_estimates.get(validated_label_name, 0))
            if count <= 0:
                count = await MetadataService.get_exact_counts(
                    db_conn, validated_graph_name, validated_label_name, "v"
                )
            properties, property_types, indexed_properties = await asyncio.gather(
                MetadataService.discover_properties(
                    db_conn, validated_graph_name, validated_label_name, "v"
                ),
                MetadataService.infer_property_types(
                    db_conn, validated_graph_name, validated_label_name, "v"
                ),
                MetadataService.get_indexed_properties(
                    db_conn, validated_graph_name, validated_label_name
                ),
            )
            return NodeLabel(
                label=label_name,
                count=int(count),
                properties=properties,
                property_types=property_types,
                indexed_properties=indexed_properties,
            )

        node_labels: list[NodeLabel] = list(
            await asyncio.gather(*[build_node_label(row) for row in node_label_rows])
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
        edge_count_estimates = await MetadataService.get_label_count_estimates(
            db_conn, validated_graph_name, "e"
        )

        async def build_edge_label(row: dict) -> EdgeLabel:
            label_name = row["label_name"]
            validated_label_name = validate_label_name(label_name)
            count = int(edge_count_estimates.get(validated_label_name, 0))
            if count <= 0:
                count = await MetadataService.get_exact_counts(
                    db_conn, validated_graph_name, validated_label_name, "e"
                )

            properties, property_types, indexed_properties = await asyncio.gather(
                MetadataService.discover_properties(
                    db_conn, validated_graph_name, validated_label_name, "e"
                ),
                MetadataService.infer_property_types(
                    db_conn, validated_graph_name, validated_label_name, "e"
                ),
                MetadataService.get_indexed_properties(
                    db_conn, validated_graph_name, validated_label_name
                ),
            )

            numeric_stats = await MetadataService.get_numeric_property_statistics_for_label(
                db_conn,
                validated_graph_name,
                validated_label_name,
                properties=properties,
            )

            property_stats = [
                PropertyStatistics(property=prop, min=stats["min"], max=stats["max"])
                for prop, stats in numeric_stats.items()
                if prop in properties
                and stats.get("min") is not None
                and stats.get("max") is not None
            ]

            return EdgeLabel(
                label=label_name,
                count=int(count),
                properties=properties,
                property_types=property_types,
                indexed_properties=indexed_properties,
                property_statistics=property_stats,
            )

        edge_labels: list[EdgeLabel] = list(
            await asyncio.gather(*[build_edge_label(row) for row in edge_label_rows])
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


@router.get("/{graph_name}/meta-graph")
async def get_meta_graph(
    graph_name: str,
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
) -> MetaGraphResponse:
    """Get meta-graph view showing label-to-label relationship patterns."""
    try:
        # Validate graph name format (prevents SQL injection)
        validated_graph_name = validate_graph_name(graph_name)

        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
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
            logger.warning("Meta-graph Cypher query failed, falling back to empty: %s", e)
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


@router.post("/{graph_name}/nodes/{node_id}/expand")
async def expand_node_neighborhood(
    graph_name: str,
    node_id: str,
    request: NodeExpandRequest,
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
) -> NodeExpandResponse:
    """Expand the neighborhood of a node up to a specified depth."""
    try:
        # Validate graph name
        validated_graph_name = validate_graph_name(graph_name)

        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
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

        # Build Cypher query for neighborhood expansion.
        #
        # We need every node and every relationship along each path so that
        # depth > 1 expansions don't drop intermediate hops. Using two UNWIND
        # clauses produces (path_node, rel) pairs per path; the Python layer
        # below dedupes by id, so the multiplication is bounded and harmless.
        #
        # `LIMIT` is applied to whole paths *before* UNWIND so very dense
        # neighbourhoods can't blow up the result set.
        depth = request.depth
        limit = request.limit
        direction = request.direction

        # Build relationship pattern.
        # depth is validated by Pydantic (1..5); inline it because AGE doesn't
        # support parameter binding inside `[*..]`.
        # edge_labels are validated via validate_label_name before inlining.
        if request.edge_labels:
            validated_labels = [validate_label_name(lbl) for lbl in request.edge_labels]
            rel_type_filter = "|".join(validated_labels)
            rel_pattern = f"[:{rel_type_filter}*1..{depth}]"
        else:
            rel_pattern = f"[*1..{depth}]"

        if direction == "out":
            path_pattern = f"(n)-{rel_pattern}->(m)"
        elif direction == "in":
            path_pattern = f"(n)<-{rel_pattern}-(m)"
        else:
            path_pattern = f"(n)-{rel_pattern}-(m)"

        cypher_query = f"""
            MATCH path = {path_pattern}
            WHERE id(n) = $node_id
            WITH n, path
            LIMIT $limit
            UNWIND nodes(path) as pn
            UNWIND relationships(path) as rel
            RETURN DISTINCT n, pn, rel
        """

        # Count query: cheap scalar — same direction/label filters, uses same depth as main query.
        # Item 1: rel_type_filter is already built from validate_label_name()-sanitised labels above.
        # Item 17: use *1..{depth} to match the same traversal depth as the main expansion query.
        if request.edge_labels:
            count_rel = f"[:{rel_type_filter}*1..{depth}]"
        else:
            count_rel = f"[*1..{depth}]"

        if direction == "out":
            count_pattern = f"(n)-{count_rel}->(m)"
        elif direction == "in":
            count_pattern = f"(n)<-{count_rel}-(m)"
        else:
            count_pattern = f"(n)-{count_rel}-(m)"

        count_query = f"""
            MATCH {count_pattern}
            WHERE id(n) = $node_id
            RETURN count(DISTINCT m) as total
        """

        # Execute both queries; run them concurrently to minimise latency.
        params = {"node_id": node_id_int, "limit": limit}
        count_params = {"node_id": node_id_int}
        raw_rows, count_rows = await asyncio.gather(
            db_conn.execute_cypher(validated_graph_name, cypher_query, params=params),
            db_conn.execute_cypher(validated_graph_name, count_query, params=count_params),
        )

        # Extract total_neighbours from count result.
        total_neighbours = 0
        for row in count_rows:
            for val in row.values():
                parsed = AgTypeParser.parse(val)
                if isinstance(parsed, (int, float)):
                    total_neighbours = int(parsed)
                    break

        # Parse expand results and extract nodes/edges
        all_nodes = {}
        all_edges = []
        edge_ids = set()

        for raw_row in raw_rows:
            for col_name, agtype_value in raw_row.items():
                parsed_value = AgTypeParser.parse(agtype_value)

                if isinstance(parsed_value, dict):
                    # Could be a node or a list of relationships
                    if parsed_value.get("type") == "node":
                        elem_node_id = parsed_value.get("id")
                        if elem_node_id:
                            all_nodes[str(elem_node_id)] = parsed_value
                    elif parsed_value.get("type") == "edge":
                        elem_edge_id = parsed_value.get("id")
                        if elem_edge_id and elem_edge_id not in edge_ids:
                            all_edges.append(parsed_value)
                            edge_ids.add(elem_edge_id)
                elif isinstance(parsed_value, list):
                    # Could be a list of relationships
                    for item in parsed_value:
                        if isinstance(item, dict):
                            if item.get("type") == "edge":
                                elem_edge_id = item.get("id")
                                if elem_edge_id and elem_edge_id not in edge_ids:
                                    all_edges.append(item)
                                    edge_ids.add(elem_edge_id)
                            elif item.get("type") == "node":
                                elem_node_id = item.get("id")
                                if elem_node_id:
                                    all_nodes[str(elem_node_id)] = item

        # Convert nodes dict to list
        nodes_list = list(all_nodes.values())

        return NodeExpandResponse(
            nodes=nodes_list,
            edges=all_edges,
            node_count=len(nodes_list),
            edge_count=len(all_edges),
            truncated=total_neighbours > len(nodes_list),
            total_neighbours=total_neighbours,
        )

    except APIException:
        raise
    except Exception as e:
        logger.exception(f"Error expanding neighborhood for node {node_id} in graph {graph_name}")
        api_exc = translate_db_error(e, context={"graph": graph_name, "node_id": node_id})
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
)
async def find_shortest_path(
    graph_name: str,
    request: ShortestPathRequest,
    db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)],
) -> ShortestPathResponse:
    """Find shortest path between two nodes using variable-length path matching."""
    try:
        validated_graph_name = validate_graph_name(graph_name)

        # Verify graph exists
        graph_check = """
            SELECT graphid FROM ag_catalog.ag_graph WHERE name = %(graph_name)s
        """
        graph_id = await db_conn.execute_scalar(graph_check, {"graph_name": validated_graph_name})
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
        logger.exception(f"Error finding shortest path in graph {graph_name}: {e}")
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
