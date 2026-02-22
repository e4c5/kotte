# Troubleshooting Guide

Common errors, debugging tips, and solutions for the Kotte Apache AGE Graph Visualizer.

---

## Authentication & Session

### "Authentication required" (401)

- **Cause**: No valid session or session expired.
- **Solution**: Log in again. Ensure cookies are enabled and not blocked.

### "Invalid username or password" (401)

- **Cause**: Wrong credentials or user doesn't exist.
- **Solution**: Check username and password. Default dev: `admin` / `admin`.

### Session lost after page refresh

- **Cause**: Session cookie not persisted or wrong domain.
- **Solution**: Ensure frontend and backend share the same origin or CORS is configured for credentials.

---

## Database Connection

### "Database connection not established" (500)

- **Cause**: Not connected to PostgreSQL or connection dropped.
- **Solution**: Connect to the database via the Connection panel. Verify host, port, database name, user, and password.

### "Connection failed" when connecting

- **Cause**: Invalid credentials, wrong host/port, firewall, or PostgreSQL not running.
- **Solution**:
  - Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
  - Check `pg_hba.conf` allows connections from your host
  - Ensure Apache AGE is installed: `CREATE EXTENSION IF NOT EXISTS age;`

---

## Graph Operations

### "Graph 'X' not found" (404)

- **Cause**: Graph doesn't exist or name is wrong.
- **Solution**: List graphs to see valid names. Create the graph first:  
  `SELECT * FROM ag_catalog.create_graph('graph_name');`

### "Graph name must contain only letters, numbers, and underscores" (400)

- **Cause**: Invalid graph name (e.g. hyphen, space, special chars).
- **Solution**: Use names like `my_graph`, `Graph1`, `_private`.

---

## Query Execution

### "Cypher syntax error" (422)

- **Cause**: Invalid Cypher syntax.
- **Solution**: Check the error message for the offending part. Common issues:
  - Missing or extra parentheses/brackets
  - Typo in clause (e.g. `RETRUN` instead of `RETURN`)
  - Invalid property/relationship syntax

### "Property or column does not exist"

- **Cause**: Referenced property or label doesn't exist on the graph.
- **Solution**: Check metadata for available labels and properties. Use `OPTIONAL MATCH` if property may be missing.

### "Label or relation does not exist"

- **Cause**: Node or edge label doesn't exist.
- **Solution**: Verify label names in graph metadata. Create nodes/edges with the correct labels first.

### "Query exceeds maximum length" (413)

- **Cause**: Query is over 1MB.
- **Solution**: Split the query or use parameters instead of inline values.

### Query timeout

- **Cause**: Query took too long (default timeout).
- **Solution**: Add LIMIT, use indexes, simplify the query, or increase timeout in configuration.

---

## Constraints & Import

### "unique constraint violated"

- **Cause**: Inserting duplicate value for a unique property (e.g. duplicate node ID).
- **Solution**: Ensure unique values or update existing nodes instead of creating duplicates.

### "referential integrity" / foreign key violation

- **Cause**: Edge references a node that doesn't exist (invalid `start_id` or `end_id`).
- **Solution**: Create nodes before edges. Verify node IDs in the import data.

### "not null constraint violated"

- **Cause**: Required property is null.
- **Solution**: Provide values for all required properties.

### CSV import fails mid-way

- **Cause**: Invalid row, constraint violation, or connection issue.
- **Solution**: Check the error message for the failing row. Fix data and retry. Import runs in a transaction, so no partial data is committed.

---

## Performance

### Slow metadata or meta-graph

- **Cause**: Large graph, no indexes, or outdated statistics.
- **Solution**: See [PERFORMANCE.md](PERFORMANCE.md). Add indexes on `id`, `start_id`, `end_id`. Run migration script for existing graphs.

### Slow variable-length path queries

- **Cause**: `[*1..n]` pattern scans many paths.
- **Solution**: Use a lower `max_depth`. Ensure indexes exist.

---

## Development

### Backend tests fail with "Requires session middleware"

- **Solution**: Use the test harness: `client` fixture uses `test_app` with CSRF and rate limit disabled. Run:  
  `pytest tests/test_auth.py tests/test_session.py tests/test_middleware.py -v`

### Frontend build errors

- **Solution**: Ensure Node.js 18+. Run `npm install` and `npm run build`.
