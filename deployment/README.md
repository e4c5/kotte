# Kotte Deployment with Docker Compose

Run Apache AGE and the Kotte visualizer with a single command.

## Quick Start

```bash
cd deployment
docker-compose up -d
```

Then open:
- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/api/docs

## What Runs

| Service   | Port | Description                          |
|-----------|------|--------------------------------------|
| **age**   | 5432 | Apache AGE (PostgreSQL + graph extension) |
| **backend** | 8000 | FastAPI backend                     |
| **frontend** | 5173 | React + Vite dev server             |

## Connecting to the Database

When you first open the visualizer at http://localhost:5173, connect with:

| Field    | Value     |
|----------|-----------|
| Host     | `age`     |
| Port     | `5432`    |
| Database | `postgres`|
| User     | `postgres`|
| Password | `postgres`|

> **Note:** Use `age` as the host—the backend runs in Docker and connects to the AGE container by its service name. The AGE container is also exposed on port 5432 on your host; if that port is already in use, change the mapping in `docker-compose.yml` (e.g. `"5433:5432"`).

## Configuration

### Environment Variables

Create a `.env` file in the `deployment/` folder to override defaults:

```env
# Required for production
SESSION_SECRET_KEY=your-secure-key-here

# Optional: change AGE port if 5432 is in use
# (update ports in docker-compose.yml)
```

### Persistent Data

- **AGE data:** Stored in volume `age-data` (PostgreSQL data)
- **Saved connections:** Stored in volume `backend-data` (encrypted credentials)

## Commands

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Creating a Test Graph

Connect to AGE and create a graph:

```bash
docker exec -it kotte-age psql -U postgres -d postgres -c "SELECT * FROM ag_catalog.create_graph('my_graph');"
```

Or connect via the Kotte UI and run Cypher to create nodes and edges.
