# Kotte - Apache AGE Visualizer

A graph visualizer for Apache AGE with a FastAPI backend and React frontend. Connect to your PostgreSQL database with the AGE extension, run Cypher queries, and explore graph data through an interactive visualization or table view.

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+, PostgreSQL 14+ with Apache AGE extension

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Or use the Makefile:

```bash
make install-backend install-frontend
make dev-backend    # Terminal 1
make dev-frontend   # Terminal 2
```

- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/api/docs

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed setup and database preparation.

## Essential Configuration

Configuration is done via environment variables. Create a `.env` file in the `backend/` directory (no `.env.example` is provided; use the variables below as reference).

### Required (Production)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET_KEY` | Secret key for session signing. Generate with `openssl rand -urlsafe 32`. Required in production. |

### Database (Connection Defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `postgres` | Default database name |
| `DB_USER` | `postgres` | Default user |
| `DB_PASSWORD` | `postgres` | Default password |

*Note: Users connect through the UI with their own credentials; these defaults are for server-side operations.*

### Session & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_COOKIE_NAME` | `kotte_session` | Cookie name for sessions |
| `SESSION_MAX_AGE` | `3600` | Session lifetime in seconds (1 hour) |
| `SESSION_IDLE_TIMEOUT` | `1800` | Idle timeout in seconds (30 minutes) |
| `CSRF_ENABLED` | `true` | Enable CSRF protection |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | `60` | Requests per minute per IP |
| `RATE_LIMIT_PER_USER` | `100` | Requests per minute per user |

### Query & Visualization Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `QUERY_TIMEOUT` | `300` | Query timeout in seconds (5 minutes) |
| `QUERY_MAX_RESULT_ROWS` | `100000` | Maximum rows returned by a query |
| `QUERY_SAFE_MODE` | `false` | When `true`, rejects mutating queries (read-only) |
| `MAX_NODES_FOR_GRAPH` | `5000` | Maximum nodes shown in graph view |
| `MAX_EDGES_FOR_GRAPH` | `10000` | Maximum edges shown in graph view |

### Import Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `IMPORT_MAX_FILE_SIZE` | `104857600` | Max CSV file size in bytes (100MB) |
| `IMPORT_MAX_ROWS` | `1000000` | Max rows per import |

### CORS & Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed origins (comma-separated) |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level |

### Credential Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CREDENTIAL_STORAGE_TYPE` | `json_file` | Storage type: `json_file`, `sqlite`, `postgresql`, `redis` |
| `CREDENTIAL_STORAGE_PATH` | `./data/connections.json` | Path for `json_file` storage |
| `MASTER_ENCRYPTION_KEY` | *(empty)* | Encryption key for stored credentials. **Development:** If unset, a key is auto-generated on first use and persisted to `.master_encryption_key` (next to the connections file), so credentials in `connections.json` remain encrypted. **Production:** Must be set—otherwise the app raises an error when using credential storage. For non-development environments with `CREDENTIAL_STORAGE_TYPE=json_file`, set this before persisting connections, or consider alternative storage (`sqlite`, `postgresql`, `redis`). |

## Project Structure

```text
kotte/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API routes (session, graph, query)
│   │   ├── core/     # Auth, db, config
│   │   ├── models/   # Pydantic models
│   │   └── services/ # Business logic
│   └── tests/
├── frontend/         # React frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── stores/
│   └── tests/
└── docs/             # Documentation
```

## Using Kotte

1. **Connect** – On first load, enter your PostgreSQL connection details (host, port, database, user, password).
2. **Select a graph** – Choose an AGE graph from the metadata sidebar.
3. **Run queries** – Use the Cypher query editor; results appear as graph or table.
4. **Explore** – Toggle graph/table view, inspect metadata, export results, and browse query history.

## Key Features

- **Interactive Graph Visualization** - D3.js-powered force-directed layouts with zoom, pan, and node pinning
- **Cypher Query Editor** - Write and execute Cypher queries with syntax highlighting and history
- **Multiple View Modes** - Switch between interactive graph visualization and table view
- **Saved Connections** - Securely store frequently-used database connections with AES-256-GCM encryption
- **Metadata Explorer** - Browse graphs, node labels, edge types, and discover properties
- **Export Capabilities** - Export query results as CSV or JSON
- **Session Management** - Secure session-based authentication with automatic timeout
- **Query Cancellation** - Cancel long-running queries
- **Graph Layouts** - Force-directed, hierarchical, radial, grid, and random layouts

## Documentation

- **[User Guide](docs/USER_GUIDE.md)** – Complete guide to using Kotte
- **[Quick Start](docs/QUICKSTART.md)** – Installation and setup
- **[Architecture](docs/ARCHITECTURE.md)** – Technical architecture and design
- **[Contributing](docs/CONTRIBUTING.md)** – Development guide for contributors

## API Documentation

When the backend is running:

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

See [Architecture documentation](docs/ARCHITECTURE.md) for detailed API reference.

## Security

- **Session-based authentication** with secure HttpOnly cookies
- **Encrypted credential storage** using AES-256-GCM
- **Parameterized queries** for SQL injection protection
- **CSRF protection** on state-changing requests
- **Rate limiting** (configurable per-IP and per-user)
- **Input validation** with strict Pydantic schemas
- **Optional read-only mode** via `QUERY_SAFE_MODE`

See [Contributing guide](docs/CONTRIBUTING.md) for detailed security implementation.

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

Via Makefile: `make test-backend` and `make test-frontend`

See [Contributing guide](docs/CONTRIBUTING.md) for testing guidelines.
