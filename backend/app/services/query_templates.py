"""Pre-built Cypher query templates for common graph patterns."""

from typing import Any, Dict, List

# Template format: {name, description, cypher (with optional $placeholders), params}
# Placeholders like $limit, $label, $property get filled by the caller.


QUERY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "find_influencers",
        "name": "Find Influencers",
        "description": "Nodes with the most incoming connections (high in-degree)",
        "cypher": """
            MATCH (n)-[r]->(target)
            WITH n, count(r) as in_degree
            ORDER BY in_degree DESC
            LIMIT $limit
            RETURN n, in_degree
        """.strip(),
        "params": {"limit": 10},
        "param_schema": {
            "limit": {"type": "integer", "default": 10, "description": "Max results"},
        },
    },
    {
        "id": "detect_cycles",
        "name": "Detect Cycles",
        "description": "Find cycles of length 2 (A->B->A)",
        "cypher": """
            MATCH (a)-[r1]->(b)-[r2]->(a)
            WHERE id(a) < id(b)
            RETURN a, b, r1, r2
            LIMIT $limit
        """.strip(),
        "params": {"limit": 50},
        "param_schema": {
            "limit": {"type": "integer", "default": 50, "description": "Max cycles"},
        },
    },
    {
        "id": "neighbors_count",
        "name": "Neighbor Count by Label",
        "description": "Count neighbors grouped by label",
        "cypher": """
            MATCH (n)-[]-(neighbor)
            WITH labels(neighbor)[0] as neighbor_label, count(*) as count
            RETURN neighbor_label, count
            ORDER BY count DESC
        """.strip(),
        "params": {},
        "param_schema": {},
    },
    {
        "id": "find_isolated",
        "name": "Find Isolated Nodes",
        "description": "Nodes with no connections",
        "cypher": """
            MATCH (n)
            WHERE NOT (n)--()
            RETURN n
            LIMIT $limit
        """.strip(),
        "params": {"limit": 100},
        "param_schema": {
            "limit": {"type": "integer", "default": 100, "description": "Max results"},
        },
    },
    {
        "id": "two_hop_neighbors",
        "name": "Two-Hop Neighbors",
        "description": "Nodes exactly 2 hops away from a starting node",
        "cypher": """
            MATCH (start)-[]->()-[]->(two_hop)
            WHERE id(start) = $node_id
            RETURN DISTINCT two_hop
            LIMIT $limit
        """.strip(),
        "params": {"node_id": 0, "limit": 50},
        "param_schema": {
            "node_id": {"type": "integer", "description": "Starting node ID"},
            "limit": {"type": "integer", "default": 50, "description": "Max results"},
        },
    },
]


def get_templates() -> List[Dict[str, Any]]:
    """Return all available query templates."""
    return QUERY_TEMPLATES.copy()


def get_template(template_id: str) -> Dict[str, Any] | None:
    """Get a template by ID."""
    for t in QUERY_TEMPLATES:
        if t["id"] == template_id:
            return t.copy()
    return None


def fill_template(template_id: str, params: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """
    Fill template placeholders with params. Returns (cypher, params_dict).
    """
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")

    cypher = template["cypher"]
    base_params = dict(template.get("params", {}))
    base_params.update(params or {})
    return cypher, base_params
