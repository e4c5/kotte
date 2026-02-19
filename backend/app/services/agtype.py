"""AGE agtype parsing and conversion service."""

import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AgTypeParser:
    """Parser for AGE agtype format."""

    @staticmethod
    def parse(agtype_value: Any) -> Any:
        """
        Parse an agtype value from PostgreSQL.

        AGE returns agtype as JSON-like structures. This method handles:
        - Vertices (nodes)
        - Edges
        - Paths
        - Maps
        - Lists
        - Scalars (strings, numbers, booleans, null)
        """
        if agtype_value is None:
            return None

        # If it's already a dict/list, it might be parsed JSON
        if isinstance(agtype_value, dict):
            return AgTypeParser._parse_dict(agtype_value)
        elif isinstance(agtype_value, list):
            return [AgTypeParser.parse(item) for item in agtype_value]
        elif isinstance(agtype_value, str):
            # Try to parse as JSON if it's a string
            try:
                parsed = json.loads(agtype_value)
                return AgTypeParser.parse(parsed)
            except (json.JSONDecodeError, TypeError):
                return agtype_value
        else:
            # Scalar value (int, float, bool)
            return agtype_value

    @staticmethod
    def _parse_dict(obj: Dict[str, Any]) -> Any:
        """Parse a dictionary that might be a vertex, edge, or path."""
        # Check for vertex structure
        if "id" in obj and "label" in obj:
            if "start_id" in obj and "end_id" in obj:
                # This is an edge
                return AgTypeParser._parse_edge(obj)
            else:
                # This is a vertex (node)
                return AgTypeParser._parse_vertex(obj)

        # Check for path structure (array of vertices and edges)
        if isinstance(obj, dict) and "path" in obj:
            return AgTypeParser._parse_path(obj.get("path", []))

        # Regular map/dict
        return {k: AgTypeParser.parse(v) for k, v in obj.items()}

    @staticmethod
    def _parse_vertex(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a vertex (node) from agtype."""
        node_id = obj.get("id")
        label = obj.get("label", "")
        properties = obj.get("properties", {})

        # Handle label as string or list
        if isinstance(label, list):
            label = label[0] if label else ""
        elif not isinstance(label, str):
            label = str(label)

        # Ensure properties is a dict
        if not isinstance(properties, dict):
            properties = {}

        return {
            "id": AgTypeParser._parse_id(node_id),
            "label": label,
            "properties": AgTypeParser.parse(properties),
            "type": "node",
        }

    @staticmethod
    def _parse_edge(obj: Dict[str, Any]) -> Dict[str, Any]:
        """Parse an edge from agtype."""
        edge_id = obj.get("id")
        label = obj.get("label", "")
        start_id = obj.get("start_id")
        end_id = obj.get("end_id")
        properties = obj.get("properties", {})

        # Handle label as string or list
        if isinstance(label, list):
            label = label[0] if label else ""
        elif not isinstance(label, str):
            label = str(label)

        # Ensure properties is a dict
        if not isinstance(properties, dict):
            properties = {}

        return {
            "id": AgTypeParser._parse_id(edge_id),
            "label": label,
            "source": AgTypeParser._parse_id(start_id),
            "target": AgTypeParser._parse_id(end_id),
            "properties": AgTypeParser.parse(properties),
            "type": "edge",
        }

    @staticmethod
    def _build_path_structure(elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Build path structure from a list of parsed elements.
        Expects alternating [node, edge, node, edge, ...].
        """
        if len(elements) < 2:
            return None
        segments = []
        node_ids = []
        edge_ids = []
        i = 0
        while i + 2 < len(elements):
            n1, e, n2 = elements[i], elements[i + 1], elements[i + 2]
            if (
                isinstance(n1, dict)
                and n1.get("type") == "node"
                and isinstance(e, dict)
                and e.get("type") == "edge"
                and isinstance(n2, dict)
                and n2.get("type") == "node"
            ):
                segments.append({"start_node": n1, "edge": e, "end_node": n2})
                nid = n1.get("id")
                if nid is not None and str(nid) not in {str(x) for x in node_ids}:
                    node_ids.append(str(nid))
                if e.get("id") is not None and str(e["id"]) not in {str(x) for x in edge_ids}:
                    edge_ids.append(str(e["id"]))
                n2id = n2.get("id")
                if n2id is not None and str(n2id) not in {str(x) for x in node_ids}:
                    node_ids.append(str(n2id))
                i += 2
            else:
                i += 1
        if not segments:
            return None
        first = elements[0]
        last = elements[-1]
        start_id = str(first["id"]) if isinstance(first, dict) and first.get("type") == "node" else None
        end_id = str(last["id"]) if isinstance(last, dict) and last.get("type") == "node" else None
        return {
            "type": "path",
            "segments": segments,
            "length": len(segments),
            "node_ids": node_ids,
            "edge_ids": edge_ids,
            "start_node_id": start_id,
            "end_node_id": end_id,
        }

    @staticmethod
    def _parse_path(path_data: List[Any]) -> Dict[str, Any]:
        """
        Parse a path (sequence of vertices and edges) preserving structure.
        Path format: [node, edge, node, edge, ...].
        """
        elements = []
        for item in path_data:
            parsed = AgTypeParser.parse(item)
            elements.append(parsed)
        built = AgTypeParser._build_path_structure(elements)
        if built:
            built["elements"] = elements
            return built
        return {"type": "path", "elements": elements, "segments": [], "length": 0, "node_ids": [], "edge_ids": []}

    @staticmethod
    def _parse_id(id_value: Any) -> Union[int, str]:
        """
        Parse an ID value, preserving 64-bit integers.

        AGE uses graphid which can be large integers.
        We preserve them as strings for JavaScript compatibility.
        """
        if id_value is None:
            return None

        # If it's already a string representation of a number, keep it
        if isinstance(id_value, str):
            # Try to parse as int to validate, but keep as string
            try:
                int(id_value)
                return id_value  # Keep as string for BigInt safety
            except ValueError:
                return id_value

        # If it's an int, convert to string for BigInt safety
        if isinstance(id_value, int):
            return str(id_value)

        return str(id_value)

    @staticmethod
    def extract_graph_elements(
        rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract nodes, edges, and paths from query results.

        Paths are preserved with segments when result contains path-like structures
        (alternating node-edge-node or type="path").

        Returns:
            {
                "nodes": [...],
                "edges": [...],
                "paths": [...],  # path structures with segments, node_ids, edge_ids
                "other": [...]
            }
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        paths: List[Dict[str, Any]] = []
        other: List[Dict[str, Any]] = []
        node_ids: set[str] = set()
        edge_ids: set[str] = set()

        def _add_node(n: Dict[str, Any]) -> None:
            nid = n.get("id")
            if nid is not None and str(nid) not in node_ids:
                nodes.append(n)
                node_ids.add(str(nid))

        def _add_edge(e: Dict[str, Any]) -> None:
            eid = e.get("id")
            if eid is not None and str(eid) not in edge_ids:
                edges.append(e)
                edge_ids.add(str(eid))

        for row in rows:
            for col_name, value in row.items():
                parsed = AgTypeParser.parse(value)

                if isinstance(parsed, dict):
                    if parsed.get("type") == "node":
                        _add_node(parsed)
                    elif parsed.get("type") == "edge":
                        _add_edge(parsed)
                    elif parsed.get("type") == "path":
                        paths.append(parsed)
                        for seg in parsed.get("segments", []):
                            if isinstance(seg, dict):
                                for key in ("start_node", "end_node"):
                                    n = seg.get(key)
                                    if isinstance(n, dict) and n.get("type") == "node":
                                        _add_node(n)
                                e = seg.get("edge")
                                if isinstance(e, dict) and e.get("type") == "edge":
                                    _add_edge(e)
                        for elem in parsed.get("elements", []):
                            if isinstance(elem, dict):
                                if elem.get("type") == "node":
                                    _add_node(elem)
                                elif elem.get("type") == "edge":
                                    _add_edge(elem)
                    else:
                        other.append({"column": col_name, "value": parsed})
                elif isinstance(parsed, list):
                    path_candidate = AgTypeParser._build_path_structure(parsed)
                    if path_candidate:
                        path_candidate["elements"] = parsed
                        paths.append(path_candidate)
                        for elem in parsed:
                            if isinstance(elem, dict):
                                if elem.get("type") == "node":
                                    _add_node(elem)
                                elif elem.get("type") == "edge":
                                    _add_edge(elem)
                    else:
                        for item in parsed:
                            if isinstance(item, dict):
                                if item.get("type") == "node":
                                    _add_node(item)
                                elif item.get("type") == "edge":
                                    _add_edge(item)
                        if not any(
                            isinstance(item, dict)
                            and item.get("type") in ("node", "edge")
                            for item in parsed
                        ):
                            other.append({"column": col_name, "value": parsed})
                else:
                    other.append({"column": col_name, "value": parsed})

        return {
            "nodes": nodes,
            "edges": edges,
            "paths": paths,
            "other": other,
        }

