# Performance Tuning

This document describes performance optimizations for the Kotte Apache AGE visualizer, including database indexing, query optimization, caching, and connection management.

## Database Connection Management

### Connection Pooling

Kotte uses `psycopg-pool` to manage asynchronous database connections efficiently.

- **Per-Session Pool:** Each user session maintains its own connection pool.
- **Configuration:**
  - `db_pool_min_size`: Minimum connections to keep (default: 1)
  - `db_pool_max_size`: Maximum connections (default: 10)
  - `db_pool_max_idle`: Max idle time in seconds (default: 300)
- **AGE Configuration:** Every connection in the pool is automatically initialized with `LOAD 'age'` and the correct `search_path` for AGE support.

## Caching Strategy

Kotte implements multi-level caching to reduce latency and database load.

### Backend: InMemoryCache

A TTL-based in-memory cache is used for expensive metadata operations.

- **Metadata Cache:** Caches discovered properties and label counts.
  - TTL for properties: 60 minutes.
  - TTL for count estimates: 10 minutes.
- **Invalidation:** Cache is automatically cleared when:
  - CSV import adds new data.
  - Indices are created.
  - `ANALYZE` is manually triggered.

### Frontend: apiCache

The frontend API client (`apiClient`) includes a simple in-memory cache for GET requests.

- **Graph Lists:** Cached for 5 minutes.
- **Graph Metadata:** Cached for 60 minutes.
- **Invalidation:** The frontend cache is cleared on logout or when a mutation (POST/PUT/DELETE) is performed on a related resource.

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

---

## Frontend Optimization

### Code Splitting

Kotte uses route-based code splitting to reduce the initial bundle size. Pages like `LoginPage`, `ConnectionPage`, and `WorkspacePage` are lazy-loaded only when needed.

### Memory Management

Large D3.js graph visualizations can be memory-intensive. Kotte ensures efficient memory usage by:
- **Explicit Cleanup:** Stopping force simulations and clearing SVG selections on component unmount.
- **Filtering:** Users can filter labels or properties to reduce the number of rendered elements.
- **Limits:** Hard caps on the number of nodes/edges rendered in the graph view.

---

## Statistics and Counts

### ANALYZE After Imports

After CSV import, `ANALYZE` is run on the affected table to update PostgreSQL statistics. This ensures:
- Accurate `reltuples` estimates for count display.
- Better query planning.

### Count Estimates

Metadata uses `pg_class.reltuples` for fast approximate counts. For exact counts, use `MetadataService.get_exact_counts()`.

---

## Optimization Tips

### Query Patterns

- Use `LIMIT` in Cypher when exploring: `MATCH (n:Person) RETURN n LIMIT 100`
- Prefer specific labels over `MATCH (n)`: `MATCH (n:Person)` is faster
- Variable-length paths `[*1..n]` can be slow; keep `n` small (e.g. ≤10)

### Configuration

- Set `query_timeout` appropriately for long-running queries
- Adjust `max_nodes_for_graph` and `max_edges_for_graph` if your use case needs more or fewer nodes in the graph view
