# Kotte

**Visualize and explore your Apache AGE graph data.**

Kotte connects to PostgreSQL with the Apache AGE extension and turns your graph databases into interactive visualizations. Write Cypher queries, browse metadata, and explore relationships through an intuitive interface—no configuration required beyond your connection details.

## What You Can Do

### Query & Run

- **Cypher query editor** — Write and run Cypher with syntax highlighting, parameter support, and query history. Use `Ctrl+Enter` to execute; long-running queries can be cancelled.
- **Parameterized queries** — Pass JSON parameters for dynamic, reusable queries.
- **Results as graph or table** — Toggle between an interactive graph view and a sortable, paginated table. Export to CSV or JSON.

### Explore the Graph

- **Interactive visualization** — Pan, zoom, and navigate your graph. Click nodes to inspect properties; double-click to pin or unpin nodes.
- **Expand neighborhoods** — Right-click a node and expand its neighborhood to discover connected nodes and edges on the fly.
- **Multiple layouts** — Force-directed (default), hierarchical, radial, grid, and random. Switch layouts to find the best view for your data.
- **Visual styling** — Nodes colored by label, edges by relationship type; size reflects connectivity.

### Metadata & Discovery

- **Metadata sidebar** — Browse all graphs, node labels, edge types, and approximate counts. Click a label to see sample Cypher for that type.
- **Saved connections** — Store database credentials with AES-256-GCM encryption. Reuse connections across sessions.

### Security & Reliability

- **Session-based auth** — Secure HttpOnly cookies, CSRF protection, and configurable rate limiting.
- **Encrypted credentials** — Saved connections are encrypted at rest with AES-256-GCM.
- **Read-only mode** — Optional `QUERY_SAFE_MODE` to block mutating queries for production or shared environments.

## Quick Start

```bash
cd deployment && docker compose up -d
```

Open http://localhost:5173 and connect with host `age`, database `postgres`, user `postgres`, password `postgres`.

Or run manually: [docs/QUICKSTART.md](docs/QUICKSTART.md)

## How It Works

1. **Connect** — Enter your PostgreSQL + AGE connection details
2. **Select a graph** — Pick an AGE graph from the sidebar
3. **Query** — Write Cypher in the editor; results appear as graph or table
4. **Explore** — Toggle views, inspect metadata, export, and browse history

## Documentation

- [Quick Start](docs/QUICKSTART.md) — Installation and setup
- [User Guide](docs/USER_GUIDE.md) — Using Kotte
- [Configuration](docs/CONFIGURATION.md) — Environment variables and options
- [Architecture](docs/ARCHITECTURE.md) — Technical design
- [Contributing](docs/CONTRIBUTING.md) — Development guide
