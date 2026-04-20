# Kotte Deployment with Docker Compose

Run Apache AGE and the Kotte visualizer with a single command. Two compose
files are provided — a **dev** flavour tuned for inner-loop speed (hot
reload, source mounts, permissive defaults) and a **prod** flavour tuned
for deployment (hardened, resource-limited, nginx-served frontend).

Both stacks share named volumes (`age-data`, `backend-data`), so you can
flip between them and keep your AGE data and saved credentials.

## Quick Start — Development

```bash
make compose-up-dev
# or, without make:
docker compose -f deployment/docker-compose.dev.yml up -d
```

Open:
- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/api/docs

What you get:
- Source bind-mounts on both services — edit a `.py` file and uvicorn
  reloads; edit a `.tsx` file and vite hot-swaps it.
- AGE exposed on `localhost:5432` so `psql`, dbeaver, etc. can attach.
- Permissive CORS (`localhost:5173`, `localhost:3000`, `frontend:5173`).
- No secrets required — `SESSION_SECRET_KEY` defaults to a dev-only value
  and `POSTGRES_PASSWORD` defaults to `postgres`.

## Quick Start — Production

```bash
# 1. Copy the example env file and fill in real values
cp deployment/.env.prod.example deployment/.env.prod
$EDITOR deployment/.env.prod

# 2. Start the stack
make compose-up-prod
# or, without make:
docker compose -f deployment/docker-compose.prod.yml \
    --env-file deployment/.env.prod up -d
```

Open:
- **Frontend (SPA via nginx):** http://localhost:80
- **Backend API:** http://localhost:8000/api/docs

What's different from dev:
- Frontend uses `frontend.Dockerfile.prod` → `nginx:alpine` serving the
  vite build output. Gzip, SPA fallback, immutable asset caching, and
  per-location security headers are baked in (see `nginx.conf`).
- No source mounts. The image is authoritative.
- `restart: unless-stopped` on every service.
- Per-service resource limits: age 1 GB / 1.5 CPU, backend 512 MB / 1.0
  CPU, frontend 64 MB / 0.5 CPU. Tuned for a single-tenant VM.
- Frontend container runs with `read_only: true` root, tmpfs for
  `/var/cache/nginx`, `/var/run`, `/tmp`. An RCE in nginx can't
  rewrite the SPA bundle.
- Age is not exposed on the host — only the backend (on the compose
  network) can reach it. To poke at it manually, use
  `docker exec -it kotte-age-prod psql -U postgres`.
- Secrets come from `deployment/.env.prod` (git-ignored). All four
  **REQUIRED** keys in `.env.prod.example` must be set or the stack
  won't start with sane security properties.

### Production gotcha: browser-side API routing

The shipped nginx image serves static assets only — it does **not**
reverse-proxy `/api/*` to the backend. In production you have two
clean options:

1. **Put a reverse proxy in front.** Caddy, Traefik, or Cloudflare can
   terminate TLS and route `/api/*` to `backend:8000` while sending
   everything else to `frontend:80`. This keeps the SPA's default
   `/api/...` fetch origin working unchanged. Recommended for most
   deployments.
2. **Rebuild the frontend with a different API base.** Set
   `VITE_API_BASE_URL=https://api.example.com` at build time (see
   `frontend/src/services/api.ts`), update `CORS_ORIGINS` in
   `.env.prod` to allow that origin, and the browser will talk to the
   backend directly across domains.

Wiring a reverse proxy into this stack directly is a future enhancement.

## Connecting to the Database

When you first open the visualizer at http://localhost:5173 (dev) or
http://localhost:80 (prod), connect with:

| Field    | Value                          |
|----------|--------------------------------|
| Host     | `age`                          |
| Port     | `5432`                         |
| Database | `postgres`                     |
| User     | `postgres`                     |
| Password | dev: `postgres` / prod: value from `.env.prod` |

> **Note:** Use `age` as the host — the backend runs in Docker and
> connects to the AGE container by its service name. In dev the AGE
> container is also exposed on port 5432 on your host; in prod it is
> not (there's no path for the browser to reach age directly anyway,
> and opening the port would only widen the attack surface).

## Commands

| Purpose                | Make target              | Raw docker compose                                                                                             |
|------------------------|--------------------------|----------------------------------------------------------------------------------------------------------------|
| Start dev              | `make compose-up-dev`    | `docker compose -f deployment/docker-compose.dev.yml up -d`                                                    |
| Stop dev               | `make compose-down-dev`  | `docker compose -f deployment/docker-compose.dev.yml down`                                                     |
| Tail dev logs          | `make compose-logs-dev`  | `docker compose -f deployment/docker-compose.dev.yml logs -f`                                                  |
| Start prod             | `make compose-up-prod`   | `docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod up -d`                   |
| Stop prod              | `make compose-down-prod` | `docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod down`                    |
| Tail prod logs         | `make compose-logs-prod` | `docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod logs -f`                 |
| Rebuild prod images    | `make compose-build-prod`| `docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod build`                   |
| Wipe dev volumes       | —                        | `docker compose -f deployment/docker-compose.dev.yml down -v`                                                  |
| Wipe prod volumes      | —                        | `docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod down -v`                 |

## Persistent Data

Both stacks share these named volumes (so switching between dev and prod
preserves your data):

- **`age-data`** — PostgreSQL data directory. Holds all your AGE graphs.
- **`backend-data`** — Encrypted credential store for saved connections.

Backing up is `docker volume` territory; there's no in-app export yet.

## Creating a Test Graph

Connect to AGE and create a graph:

```bash
# Dev (host port 5432 is exposed):
docker exec -it kotte-age psql -U postgres -d postgres \
    -c "SELECT * FROM ag_catalog.create_graph('my_graph');"

# Prod (age is internal — container name is different):
docker exec -it kotte-age-prod psql -U postgres -d postgres \
    -c "SELECT * FROM ag_catalog.create_graph('my_graph');"
```

Or connect via the Kotte UI and run Cypher to create nodes and edges.
