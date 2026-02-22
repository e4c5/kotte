# Kotte — Agent context

**Kotte** is a web app to visualize and explore **Apache AGE** graph data. It has a FastAPI backend and a React (TypeScript) frontend that talks to PostgreSQL with the AGE extension.

## Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, psycopg (async), uvicorn
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router, D3.js (graph viz), Zod
- **DB:** PostgreSQL 14+ with Apache AGE; Cypher via `cypher(graph_name, $$...$$)` and `agtype`

## Repo layout

```
kotte/
├── backend/app/
│   ├── api/v1/          # Routes: session, graph, query, import_csv, health, graph_delete_node
│   ├── core/            # auth, config, database, errors, middleware, security
│   ├── models/          # Pydantic request/response models
│   └── services/        # agtype (AGE parsing), metadata, connection_storage
├── frontend/src/
│   ├── components/      # GraphView, TableView, QueryEditor, GraphControls, MetadataSidebar, etc.
│   ├── pages/           # ConnectionPage, WorkspacePage
│   ├── services/        # api, session, graph, query (API client)
│   ├── stores/          # Zustand: sessionStore, graphStore, queryStore
│   └── types/           # TypeScript types for graph, query, api
├── docs/                # QUICKSTART, ARCHITECTURE, CONTRIBUTING, CONFIGURATION, ADVANCED_FEATURES
├── deployment/          # Docker Compose
└── Makefile             # install-*, dev-*, test-*, lint-*
```

## Run, test, lint

- **Run:** `make dev-backend` (port 8000) and `make dev-frontend` (port 5173). Or `cd deployment && docker compose up -d`.
- **Test:** `make test-backend` (pytest), `make test-frontend` (vitest).
- **Lint:** `make lint-backend` (ruff, black, mypy), `make lint-frontend` (eslint).

Backend needs a venv and `pip install -r requirements-dev.txt` in `backend/`. Copy `backend/.env.example` to `backend/.env` and set `SESSION_SECRET_KEY` (and DB vars if not using Docker).

## Conventions

- **Python:** PEP 8, line length 100, type hints on signatures, Google-style docstrings. Format with black, check with ruff, type-check with mypy. Use Pydantic for all API request/response and validation.
- **TypeScript:** 2 spaces, single quotes, semicolons, explicit types (avoid `any`). ESLint with `@typescript-eslint`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, etc.).

## Security (must follow)

- **No SQL from user input:** Never build Cypher or SQL with f-strings or concatenation. Always use **parameterized queries** with psycopg:
  - `await conn.execute(query, params)` with `$1, $2` (or `%(name)s`) and a tuple/dict of parameters.
- **Identifiers:** Validate graph names, labels, and other identifiers (e.g. `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$`) before using in SQL; see `app/core` and CONTRIBUTING for patterns.
- **Secrets:** No `.env` or `.master_encryption_key` in repo; credentials encrypted at rest (AES-256-GCM). See docs/CONFIGURATION.md and CONTRIBUTING.md for env and production session storage.

## API shape

- Base: `/api/v1`. Session: `POST /session/connect`, `POST /session/disconnect`. Graph: `GET /graphs`, `GET /graphs/{name}/metadata`, and graph/shortest-path/delete as in docs. Query: `POST /queries/execute`, `POST /queries/{request_id}/cancel`.
- Errors are JSON with `code`, `category`, `message`, `details`, `request_id`, `retryable`. See ARCHITECTURE.md for full request/response examples.

## Docs to use

- **Setup and run:** docs/QUICKSTART.md, README.md.
- **Design and API:** docs/ARCHITECTURE.md, docs/ADVANCED_FEATURES.md (shortest path, query templates, AGE Cypher).
- **Contributing:** docs/CONTRIBUTING.md (coding standards, testing, security, PR process).
- **Config:** docs/CONFIGURATION.md (env vars, limits, credential storage).

When changing API or behavior, update the relevant doc (ARCHITECTURE, USER_GUIDE, QUICKSTART, CONTRIBUTING) and keep code examples in sync.
