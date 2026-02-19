# Advanced AGE Features

This document describes advanced graph features available in the Kotte visualizer, including shortest path, query templates, and AGE-specific capabilities.

---

## Shortest Path

Find the shortest path between two nodes using variable-length path matching.

### Endpoint

```
POST /api/v1/graphs/{graph_name}/shortest-path
```

### Request

```json
{
  "source_id": 0,
  "target_id": 5,
  "max_depth": 10
}
```

| Field      | Type    | Description                          |
|-----------|---------|--------------------------------------|
| source_id | integer | Source node ID                       |
| target_id | integer | Target node ID                       |
| max_depth | integer | Max path length in hops (1–20, default 10) |

### Response

```json
{
  "path": [...],
  "path_length": 2,
  "nodes": [{...}, {...}],
  "edges": [{...}, {...}]
}
```

- **path_length**: Number of edges (0 if no path found)
- **nodes**: Nodes in path order
- **edges**: Edges in path order

### Implementation

Uses AGE variable-length path pattern `(src)-[*1..max_depth]-(dst)` with `ORDER BY path_length LIMIT 1` to return the shortest path. Unweighted only.

---

## Query Templates

Pre-built Cypher queries for common graph patterns.

### List Templates

```
GET /api/v1/queries/templates
```

Returns all available templates with id, name, description, cypher, and param_schema.

### Using a Template

1. Call `GET /api/v1/queries/templates` to list templates
2. Pick a template and note its `id` and `param_schema`
3. Call `POST /api/v1/queries/execute` with:
   - `graph`: graph name
   - `cypher`: the template’s `cypher` string
   - `params`: values for the template’s placeholders (e.g. `limit`, `node_id`)

### Available Templates

| ID                | Name                  | Description                                  |
|-------------------|-----------------------|----------------------------------------------|
| find_influencers  | Find Influencers      | Nodes with most incoming connections         |
| detect_cycles     | Detect Cycles         | Cycles of length 2 (A→B→A)                   |
| neighbors_count   | Neighbor Count by Label | Count neighbors grouped by label          |
| find_isolated     | Find Isolated Nodes   | Nodes with no connections                    |
| two_hop_neighbors | Two-Hop Neighbors     | Nodes exactly 2 hops from a given node       |

---

## AGE Cypher Capabilities

### Variable-Length Paths

- `(a)-[*1..5]-(b)` — paths of 1–5 hops
- `(a)-[*]-(b)` — paths of any length
- `size(relationships(path))` — path length
- `nodes(path)`, `relationships(path)` — path components

### Performance Notes

Variable-length paths can be slow for large graphs and long paths. Prefer:

- A low `max_depth` (e.g. ≤10)
- Indexing on `id`, `start_id`, `end_id` (see [PERFORMANCE.md](PERFORMANCE.md))

---

## Path Structure in Results

When a query returns path data (e.g. `MATCH path = (a)-[]->(b)-[]->(c) RETURN path`), results preserve path structure:

- **paths**: List of path objects with `segments`, `node_ids`, `edge_ids`, `start_node_id`, `end_node_id`
- **segments**: Each segment is `{start_node, edge, end_node}` for one hop
- Path nodes and edges are also included in `nodes` and `edges` for visualization
- In Graph View, path nodes and edges are highlighted (blue) when paths are present

---

## References

- [Apache AGE Cypher Manual](https://age.apache.org/age-manual/master/intro/cypher.html)
- [AGE MATCH Clause](https://age.apache.org/age-manual/master/clauses/match.html)
- [AGE List Functions](https://age.apache.org/age-manual/master/functions/list_functions.html)
