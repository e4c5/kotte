# Configuration Reference

Configuration is done via environment variables. Create a `.env` file in the `backend/` directory.

## Required (Production)

| Variable | Description |
|----------|-------------|
| `SESSION_SECRET_KEY` | Secret key for session signing. Generate with `openssl rand -urlsafe 32`. Required in production. |
| `ADMIN_PASSWORD` | Password for the built-in `admin` account. Defaults to `admin` **which must be changed in production**. |

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

## Redis (Optional, Milestone D)

Redis is **optional** and enables multi-user session and query tracking. When disabled, the backend uses in-memory stores and runs without external dependencies.

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_ENABLED` | `false` | Set to `true` to use Redis for `SessionManager` and `QueryTracker`. When `false` (default), uses in-memory dictionaries. Graceful fallback allows single-instance deployments to skip Redis. |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL (only used when `REDIS_ENABLED=true`). Format: `redis://[user:password@]host[:port][/db]` |

**When to enable:**
- Multi-user or multi-instance deployments (sessions need to be shared across workers)
- Production environments with persistence requirements
- Kubernetes deployments using pods that need to share session state

**When to disable (development/single-instance):**
- Local development
- Single-instance deployments
- Testing without external services

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
| `CORS_ORIGINS` | `["http://localhost:5173","http://localhost:3000"]` | Allowed origins. **Must be a JSON array** — `pydantic-settings` parses `List[str]` env vars as JSON, so a comma-separated value will fail at startup. A future change to `Settings.cors_origins` may add a validator that accepts both shapes; until then, use the JSON form shown. |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level |

## Credential Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `CREDENTIAL_STORAGE_TYPE` | `json_file` | Storage backend. **Only `json_file` is currently implemented** — `app/core/connection_storage.py` does not yet dispatch on this value, so other settings are inert. SQLite, PostgreSQL, and Redis backends are tracked as a Milestone D item; setting this to anything other than `json_file` today is silently a no-op. |
| `CREDENTIAL_STORAGE_PATH` | `./data/connections.json` | Path for the encrypted JSON file. |
| `MASTER_ENCRYPTION_KEY` | *(empty)* | Encryption key for stored credentials. **Development:** If unset, a key is auto-generated on first use and persisted to `.master_encryption_key` (next to the connections file). **Production:** Must be set—otherwise the app raises an error when using credential storage. |

### Key Rotation

There is currently **no automated re-encryption path**. If you rotate `MASTER_ENCRYPTION_KEY`, all
saved connections encrypted with the old key will become unreadable.

To safely rotate the key:
1. Export all saved connections from the UI (or back up `connections.json` / the SQLite file).
2. Update `MASTER_ENCRYPTION_KEY` to the new value.
3. Re-import the saved connections (they will be re-encrypted with the new key).

---

## Default Admin Credentials

> ⚠️ **Security Warning:** The default admin username is `admin` and the default password is also
> `admin`. These credentials are intentionally weak for local development and **must be changed
> before any production or publicly-accessible deployment.**

Set the `ADMIN_PASSWORD` environment variable to override the default password:

```bash
# .env
ADMIN_PASSWORD=a-long-random-secret-here
```

Alternatively, generate a strong random password and set it before starting the server:

```bash
export ADMIN_PASSWORD=$(openssl rand -base64 24)
```

The password is hashed with bcrypt on first use; the plaintext is never persisted.

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
