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
    def _parse_path(path_data: List[Any]) -> Dict[str, Any]:
        """Parse a path (sequence of vertices and edges)."""
        elements = []
        for item in path_data:
            parsed = AgTypeParser.parse(item)
            elements.append(parsed)

        return {
            "type": "path",
            "elements": elements,
        }

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
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract nodes and edges from query results.

        Returns:
            {
                "nodes": [...],
                "edges": [...],
                "other": [...]  # non-graph results (scalars, maps, etc.)
            }
        """
        nodes = []
        edges = []
        other = []
        node_ids = set()
        edge_ids = set()

        for row in rows:
            for col_name, value in row.items():
                parsed = AgTypeParser.parse(value)

                if isinstance(parsed, dict):
                    if parsed.get("type") == "node":
                        node_id = parsed.get("id")
                        if node_id and node_id not in node_ids:
                            nodes.append(parsed)
                            node_ids.add(node_id)
                    elif parsed.get("type") == "edge":
                        edge_id = parsed.get("id")
                        if edge_id and edge_id not in edge_ids:
                            edges.append(parsed)
                            edge_ids.add(edge_id)
                    else:
                        other.append({"column": col_name, "value": parsed})
                elif isinstance(parsed, list):
                    # Check if list contains graph elements
                    for item in parsed:
                        if isinstance(item, dict):
                            if item.get("type") == "node":
                                node_id = item.get("id")
                                if node_id and node_id not in node_ids:
                                    nodes.append(item)
                                    node_ids.add(node_id)
                            elif item.get("type") == "edge":
                                edge_id = item.get("id")
                                if edge_id and edge_id not in edge_ids:
                                    edges.append(item)
                                    edge_ids.add(edge_id)
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
            "other": other,
        }

