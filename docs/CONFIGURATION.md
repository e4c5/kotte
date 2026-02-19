# Configuration Reference

Configuration is done via environment variables. Create a `.env` file in the `backend/` directory.

## Required (Production)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET_KEY` | Secret key for session signing. Generate with `openssl rand -urlsafe 32`. Required in production. |

## Database (Connection Defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `postgres` | Default database name |
| `DB_USER` | `postgres` | Default user |
| `DB_PASSWORD` | `postgres` | Default password |

*Note: Users connect through the UI with their own credentials; these defaults are for server-side operations.*

## Session & Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_COOKIE_NAME` | `kotte_session` | Cookie name for sessions |
| `SESSION_MAX_AGE` | `3600` | Session lifetime in seconds (1 hour) |
| `SESSION_IDLE_TIMEOUT` | `1800` | Idle timeout in seconds (30 minutes) |
| `CSRF_ENABLED` | `true` | Enable CSRF protection |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | `60` | Requests per minute per IP |
| `RATE_LIMIT_PER_USER` | `100` | Requests per minute per user |

## Query & Visualization Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `QUERY_TIMEOUT` | `300` | Query timeout in seconds (5 minutes) |
| `QUERY_MAX_RESULT_ROWS` | `100000` | Maximum rows returned by a query |
| `QUERY_SAFE_MODE` | `false` | When `true`, rejects mutating queries (read-only) |
| `MAX_NODES_FOR_GRAPH` | `5000` | Maximum nodes shown in graph view |
| `MAX_EDGES_FOR_GRAPH` | `10000` | Maximum edges shown in graph view |

## Import Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `IMPORT_MAX_FILE_SIZE` | `104857600` | Max CSV file size in bytes (100MB) |
| `IMPORT_MAX_ROWS` | `1000000` | Max rows per import |

## CORS & Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed origins (comma-separated) |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level |

## Credential Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CREDENTIAL_STORAGE_TYPE` | `json_file` | Storage type: `json_file`, `sqlite`, `postgresql`, `redis` |
| `CREDENTIAL_STORAGE_PATH` | `./data/connections.json` | Path for `json_file` storage |
| `MASTER_ENCRYPTION_KEY` | *(empty)* | Encryption key for stored credentials. **Development:** If unset, a key is auto-generated on first use and persisted to `.master_encryption_key` (next to the connections file). **Production:** Must be set—otherwise the app raises an error when using credential storage. |

---

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
├── deployment/       # Docker Compose setup
└── docs/             # Documentation
```

## Manual Setup

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

Or use the Makefile: `make install-backend install-frontend`, then `make dev-backend` and `make dev-frontend` in separate terminals.

- **Frontend:** http://localhost:5173  
- **API docs:** http://localhost:8000/api/docs  
- **ReDoc:** http://localhost:8000/api/redoc  

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

Via Makefile: `make test-backend` and `make test-frontend`

See [Contributing guide](CONTRIBUTING.md) for testing guidelines.

## Security

- **Session-based authentication** with secure HttpOnly cookies
- **Encrypted credential storage** using AES-256-GCM
- **Parameterized queries** for SQL injection protection
- **CSRF protection** on state-changing requests
- **Rate limiting** (configurable per-IP and per-user)
- **Input validation** with strict Pydantic schemas
- **Optional read-only mode** via `QUERY_SAFE_MODE`

See [Contributing guide](CONTRIBUTING.md) for detailed security implementation.
