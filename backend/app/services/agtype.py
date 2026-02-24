"""AGE agtype parsing and conversion service."""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def _get_first_value_for_key_containing(obj: Dict[str, Any], substring: str) -> Any:
    """Return value for first key that contains substring and looks like an id key."""
    for k, v in obj.items():
        if v is None:
            continue
        k_lower = k.lower()
        if substring.lower() in k_lower and ("id" in k_lower or k_lower in ("startid", "endid")):
            return v
    return None


def _object_to_dict(value: Any) -> Optional[Dict[str, Any]]:
    """If value is an object with id/label/start/end-like attributes, return a dict for edge/vertex parsing."""
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return None
    try:
        d = getattr(value, "__dict__", None)
        if isinstance(d, dict) and "id" in d and "label" in d:
            return d
        # Try attribute access for known keys (e.g. psycopg custom type)
        for start_key in ("start_id", "startid", "startId"):
            for end_key in ("end_id", "endid", "endId"):
                if getattr(value, start_key, None) is not None and getattr(value, end_key, None) is not None:
                    return {
                        "id": getattr(value, "id", None),
                        "label": getattr(value, "label", None),
                        "start_id": getattr(value, "start_id", None),
                        "end_id": getattr(value, "end_id", None),
                        "startid": getattr(value, "startid", None),
                        "endid": getattr(value, "endid", None),
                        "properties": getattr(value, "properties", {}),
                    }
    except (TypeError, AttributeError):
        pass
    return None


def _normalize_agtype_string(s: str) -> Optional[str]:
    """Try to convert AGE native format (semicolons, unquoted keys) to JSON. Returns None if not applicable."""
    s = s.strip()
    if not s.startswith("{") or not s.endswith("}"):
        return None
    # Replace known unquoted keys with quoted keys (id, startid, endid, label, properties)
    for key in ("id", "startid", "endid", "start_id", "end_id", "label", "properties"):
        s = re.sub(rf"\b{re.escape(key)}\s*:", rf'"{key}":', s, flags=re.IGNORECASE)
    s = s.replace(";", ",")
    return s


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
            # AGE may return agtype as JSON string with type suffix (e.g. "{}::edge", "{}::vertex")
            s = agtype_value.strip()
            for suffix in ("::edge", "::vertex", "::path", "::agtype"):
                if s.endswith(suffix):
                    s = s[: -len(suffix)].strip()
                    break
            try:
                parsed = json.loads(s)
                return AgTypeParser.parse(parsed)
            except (json.JSONDecodeError, TypeError):
                # AGE native format uses semicolons; try to convert to JSON-like and re-parse
                normalized = _normalize_agtype_string(s)
                if normalized is not None:
                    try:
                        parsed = json.loads(normalized)
                        return AgTypeParser.parse(parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return agtype_value
        else:
            # Custom type (e.g. psycopg adapter)? Try to convert to dict
            obj = _object_to_dict(agtype_value)
            if obj is not None:
                return AgTypeParser._parse_dict(obj)
            # Scalar value (int, float, bool)
            return agtype_value

    @staticmethod
    def _is_edge(obj: Dict[str, Any]) -> bool:
        """True if dict looks like an AGE edge (has endpoint ids in any known format)."""
        if "id" not in obj or "label" not in obj:
            return False
        # Already-parsed edge (from a previous parse() call)
        if obj.get("source") is not None and obj.get("target") is not None:
            return True
        # Explicit keys we know (raw AGE format)
        if obj.get("start_id") is not None and obj.get("end_id") is not None:
            return True
        if obj.get("startid") is not None and obj.get("endid") is not None:
            return True
        if obj.get("startId") is not None and obj.get("endId") is not None:
            return True
        if obj.get("start_vertex_id") is not None and obj.get("end_vertex_id") is not None:
            return True
        # Fallback: any key containing 'start' and some key containing 'end' (for unknown AGE variants)
        start_val = None
        end_val = None
        for k, v in obj.items():
            if v is None:
                continue
            k_lower = k.lower()
            if "start" in k_lower and ("id" in k_lower or k_lower == "startid"):
                start_val = v
            elif "end" in k_lower and ("id" in k_lower or k_lower == "endid"):
                end_val = v
        return start_val is not None and end_val is not None

    @staticmethod
    def _parse_dict(obj: Dict[str, Any]) -> Any:
        """Parse a dictionary that might be a vertex, edge, or path."""
        # Check for vertex structure
        if "id" in obj and "label" in obj:
            if AgTypeParser._is_edge(obj):
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
        """Parse an edge from agtype. Supports start_id/end_id, startid/endid, and already-parsed source/target."""
        edge_id = obj.get("id")
        label = obj.get("label", "")
        start_id = obj.get("start_id")
        if start_id is None:
            start_id = obj.get("startid")
        if start_id is None:
            start_id = obj.get("startId")
        if start_id is None:
            start_id = obj.get("start_vertex_id")
        if start_id is None:
            start_id = obj.get("source")
        if start_id is None:
            start_id = _get_first_value_for_key_containing(obj, "start")
        end_id = obj.get("end_id")
        if end_id is None:
            end_id = obj.get("endid")
        if end_id is None:
            end_id = obj.get("endId")
        if end_id is None:
            end_id = obj.get("end_vertex_id")
        if end_id is None:
            end_id = obj.get("target")
        if end_id is None:
            end_id = _get_first_value_for_key_containing(obj, "end")
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

        # If we have edges but no nodes (e.g. query was RETURN r), synthesize placeholder nodes
        # from edge endpoints so the graph view can render
        if edges and not nodes:
            for e in edges:
                sid = e.get("source")
                tid = e.get("target")
                if sid is not None and sid not in node_ids:
                    nodes.append({
                        "id": sid,
                        "label": "",
                        "properties": {},
                        "type": "node",
                    })
                    node_ids.add(sid)
                if tid is not None and tid not in node_ids:
                    nodes.append({
                        "id": tid,
                        "label": "",
                        "properties": {},
                        "type": "node",
                    })
                    node_ids.add(tid)
        elif edges:
            # Ensure every edge source/target has a node (placeholder if missing)
            for e in edges:
                sid = e.get("source")
                tid = e.get("target")
                if sid is not None and sid not in node_ids:
                    nodes.append({
                        "id": sid,
                        "label": "",
                        "properties": {},
                        "type": "node",
                    })
                    node_ids.add(sid)
                if tid is not None and tid not in node_ids:
                    nodes.append({
                        "id": tid,
                        "label": "",
                        "properties": {},
                        "type": "node",
                    })
                    node_ids.add(tid)

        return {
            "nodes": nodes,
            "edges": edges,
            "paths": paths,
            "other": other,
        }

