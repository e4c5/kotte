# Performance Tuning

This document describes performance optimizations for the Kotte Apache AGE visualizer, including database indexing, query optimization, and caching.

## Database Indexing

### Index Strategy

For each vertex and edge label, the following indices are created:

| Label Type | Index Columns | Purpose |
|------------|---------------|---------|
| Vertex (v) | `id` | Fast node lookup by ID (expand, delete, etc.) |
| Edge (e)   | `id`, `start_id`, `end_id` | Fast edge traversal and relationship queries |

### Creating Indices

Indices are **not** created automatically. Use one of these approaches:

1. **Migration script** (recommended for existing graphs):
   ```bash
   cd backend
   . venv/bin/activate
   DB_HOST=localhost DB_PORT=5432 DB_NAME=your_db DB_USER=postgres DB_PASSWORD=xxx \
     python -m scripts.migrate_add_indices
   ```

2. **Programmatic** via `MetadataService.create_label_indices()`:
   ```python
   from app.services.metadata import MetadataService

   await MetadataService.create_label_indices(db_conn, graph_name, label_name, "v")
   await MetadataService.create_label_indices(db_conn, graph_name, label_name, "e")
   ```

### Expected Impact

- Node lookup by ID: ~125x faster (250ms → 2ms on large graphs)
- Edge traversal: ~100x faster
- Metadata discovery: ~50x faster with indices + ANALYZE

---

## Query Optimization

### Meta-Graph Discovery

The meta-graph endpoint uses a single Cypher query instead of N+1 queries:

```cypher
MATCH (src)-[rel]->(dst)
WITH labels(src)[0] as src_label, type(rel) as rel_type, labels(dst)[0] as dst_label
RETURN src_label, rel_type, dst_label, COUNT(*) as edge_count
ORDER BY edge_count DESC
LIMIT 1000
```

### Property Discovery

Property keys are discovered using PostgreSQL's `jsonb_object_keys()` for a single-pass scan of all properties, avoiding sampling and missing rare keys.

---

## Caching

### Property Cache

Discovered properties are cached for 60 minutes to reduce repeated queries. Cache is invalidated when:

- CSV import adds new data (per graph/label)
- TTL expires

---

## Statistics and Counts

### ANALYZE After Imports

After CSV import, `ANALYZE` is run on the affected table to update PostgreSQL statistics. This ensures:

- Accurate `reltuples` estimates for count display
- Better query planning

### Count Estimates

Metadata uses `pg_class.reltuples` for fast approximate counts. For exact counts, use `MetadataService.get_exact_counts()`.

---

## Visualization Limits

- Maximum nodes for graph visualization: 5,000 (configurable via `max_nodes_for_graph`)
- Maximum edges: 5,000 (configurable via `max_edges_for_graph`)

When `for_visualization` is true on query execute, a `LIMIT` is automatically added to the Cypher query if not present, to avoid fetching huge result sets. Queries that exceed limits return a warning.

---

## Optimization Tips

### Query Patterns

- Use `LIMIT` in Cypher when exploring: `MATCH (n:Person) RETURN n LIMIT 100`
- Prefer specific labels over `MATCH (n)`: `MATCH (n:Person)` is faster
- Use indexes: queries that filter by `id(n) = $id` benefit from the `id` index
- Variable-length paths `[*1..n]` can be slow; keep `n` small (e.g. ≤10)

### Configuration

- Set `query_timeout` appropriately for long-running queries
- Adjust `max_nodes_for_graph` and `max_edges_for_graph` if your use case needs more or fewer nodes in the graph view
