# Kotte User Guide

A guide for using the Kotte Apache AGE Graph Visualizer, including authentication, graph operations, query execution, and advanced features.

---

## Prerequisites

- PostgreSQL 14+ with Apache AGE extension
- See [QUICKSTART.md](QUICKSTART.md) for setup

---

## Authentication & Session

### Login

1. Open the Kotte frontend and log in with your credentials.
2. Default dev user: `admin` / `admin` (change in production).
3. The session is stored in a cookie (`kotte_session`).

### Database Connection

1. After login, connect to your PostgreSQL database.
2. Provide host, port, database name, user, and password.
3. The connection is stored in the session and used for all graph operations.

### Session Timeout

- Session expires after 1 hour of inactivity by default.
- Reconnect if you see "Authentication required" or "Database connection lost".

---

## Graph Operations

### List Graphs

- Navigate to the graph list to see all AGE graphs in the connected database.
- Each graph shows its name and ID.

### Graph Metadata

- Select a graph to view its metadata: node labels, edge labels, property schemas.
- Metadata is cached for performance; it refreshes on CSV import.

### Create Graph

- Use the "Create Graph" action to create a new AGE graph.
- Graph names must be valid PostgreSQL identifiers (letters, numbers, underscores, start with letter/underscore).

---

## Running Queries

### Cypher Basics

- Use the query editor to run Cypher (openCypher) queries against the selected graph.
- Example: `MATCH (n:Person) RETURN n LIMIT 10`
- See [Apache AGE Cypher Manual](https://age.apache.org/age-manual/master/intro/cypher.html).

### Query Limits

- Queries are limited to 1MB in length.
- For visualization, a LIMIT is applied when `for_visualization` is true to avoid browser overload.

### Query Parameters

- Use parameterized queries for safety: `MATCH (n {id: $id}) RETURN n`
- Pass parameters in the `params` field when executing.

---

## Advanced Features

### Shortest Path

- Use the Shortest Path feature to find the shortest path between two nodes.
- Specify source node ID, target node ID, and max depth (1–20).
- See [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md).

### Query Templates

- Pre-built templates: Find Influencers, Detect Cycles, Neighbor Count, Find Isolated Nodes, Two-Hop Neighbors.
- List templates via `GET /api/v1/queries/templates` and use their Cypher with appropriate params.

### Path Visualization

- Queries that return path data highlight path nodes and edges in blue in the Graph View.
- Example: `MATCH path = (a)-[]->(b)-[]->(c) RETURN path`

---

## Importing Data

### CSV Import

- Import CSV files to create nodes and edges.
- Configure graph name, label, columns, and mappings.
- Large imports run in batches within a transaction.

### Best Practices

- Use indexes on `id`, `start_id`, `end_id` for large graphs (see [PERFORMANCE.md](PERFORMANCE.md)).
- Run `ANALYZE` after imports for better query plans (done automatically).

---

## Error Handling

- **AUTH_REQUIRED**: Log in and connect to the database.
- **GRAPH_NOT_FOUND**: Graph name is invalid or doesn't exist.
- **GRAPH_CONSTRAINT_VIOLATION**: Unique, foreign key, or check constraint failed.
- **CYPHER_SYNTAX_ERROR**: Check the Cypher query syntax; the error message includes context.
- **DB_UNAVAILABLE**: Database connection failed or lost; reconnect.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more details.
