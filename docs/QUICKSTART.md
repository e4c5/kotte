# Quick Start Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ with Apache AGE extension
- Docker (optional: for [Docker Compose deployment](../deployment/README.md) or devcontainer)

## Setup

### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your database settings

# Run backend
uvicorn app.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`
API docs at `http://localhost:8000/api/docs`

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

**Automated quick start (Playwright):** To avoid typing login and connection details every time, use the Playwright script. With the backend and frontend running:

```bash
cd frontend
npm install
npx playwright install chromium
npm run quick-start:headed
```

The script logs in as admin/admin, fills the connection form (host, port, database, user, password), tests the connection, and opens the workspace. Default connection: `localhost:5455`, database `postgresDB`, user `postgresUser`, password `postgresPW`. Override with env vars: `KOTTE_DB_HOST`, `KOTTE_DB_PORT`, `KOTTE_DB_NAME`, `KOTTE_DB_USER`, `KOTTE_DB_PASSWORD`. To leave the browser open after reaching the workspace: `KEEP_BROWSER_OPEN=1 npm run quick-start:headed`.

### 3. Database Setup

Ensure PostgreSQL is running with Apache AGE extension:

```sql
CREATE EXTENSION IF NOT EXISTS age;
```

Create a test graph:

```sql
SELECT * FROM ag_catalog.create_graph('test_graph');
```

For a **sample graph with nodes and edges** that work with Graph View, run [docs/sample-graph-test_graph.sql](sample-graph-test_graph.sql) against your database (e.g. `psql -h localhost -p 5455 -U postgresUser -d postgresDB -f docs/sample-graph-test_graph.sql`). Then in Kotte, select graph `test_graph` and run: `MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50`.

## Docker Compose (Simplest)

Run everything—Apache AGE, backend, and frontend—with one command:

```bash
cd deployment
docker compose up -d
```

Open http://localhost:5173 and connect with host `age`, database `postgres`, user `postgres`, password `postgres`. See [deployment/README.md](../deployment/README.md) for details.

## Using Makefile

```bash
# Install dependencies
make install-backend
make install-frontend

# Run development servers
make dev-backend    # Terminal 1
make dev-frontend   # Terminal 2

# Run tests
make test-backend
make test-frontend

# Lint code
make lint-backend
make lint-frontend
```

## Development Workflow

1. Start PostgreSQL with AGE
2. Start backend server (`make dev-backend`)
3. Start frontend server (`make dev-frontend`)
4. Open browser to `http://localhost:5173`
5. Log in with the default credentials (`admin` / `admin`) — see the security note below
6. Connect to your database
7. Start exploring graphs!

## Security Note — Default Credentials

> ⚠️ The default login is **admin / admin**. This is intentional for local development only.
> Before exposing the application to any network, set a strong password via the
> `ADMIN_PASSWORD` environment variable (see [CONFIGURATION.md](CONFIGURATION.md)):
>
> ```bash
> export ADMIN_PASSWORD=$(openssl rand -base64 24)
> ```

## Next Steps

- Implement D3.js graph visualization
- Add query editor with history
- Implement CSV import
- Add graph interaction features
- Write comprehensive tests

