# Kotte — Agent context

**Kotte** is a web app to visualize and explore **Apache AGE** graph data. It has a FastAPI backend and a React (TypeScript) frontend that talks to PostgreSQL with the AGE extension.

## Stack

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, psycopg (async) with connection pooling, uvicorn
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Zustand, React Router, D3.js (graph viz), Zod
- **DB:** PostgreSQL 14+ with Apache AGE; Cypher via `cypher(graph_name, $$...$$)` and `agtype`

## Repo layout

```
kotte/
├── backend/app/
│   ├── api/v1/          # Routes: session, graph, query, import_csv, health
│   ├── core/            # auth, config, database, errors, logging, middleware, metrics
│   │   └── database/    # Modular DB: connection (pool), cypher, manager, utils
│   ├── models/          # Pydantic request/response models
│   └── services/        # agtype (AGE), metadata, cache, user
├── frontend/src/
│   ├── components/      # GraphView, TableView, GraphControls, TabBar, etc.
│   │   └── GraphControls/ # Decomposed control tabs
│   ├── hooks/           # useGraphExport, useCache, etc.
│   ├── pages/           # ConnectionPage, LoginPage, WorkspacePage (Lazy loaded)
│   ├── services/        # api (with caching), session, graph, query
│   ├── stores/          # Zustand: sessionStore, graphStore, queryStore, settingsStore
│   └── utils/           # graphLayouts, graphStyles, apiCache, nodeColors
├── docs/                # Architecture, contributing, configuration, features
├── deployment/          # Docker Compose and Dockerfiles
└── Makefile             # install-*, dev-*, test-*, lint-*
```

## Performance & Monitoring

- **Connection Pooling:** Uses `psycopg-pool` for efficient async database connections. Managed per-session.
- **Caching:** 
  - **Backend:** `InMemoryCache` with TTL for graph metadata and label counts.
  - **Frontend:** `apiCache` for GET requests (metadata, graph lists) to reduce redundant API calls.
- **Logging:** Structured JSON logging enabled by default in production. Includes `request_id` for tracing.
- **Metrics:** Prometheus metrics exposed for HTTP requests, database queries, cache hits/misses, and pool status.
- **Frontend Optimization:** Route-based code splitting (lazy loading), D3 memory management (explicit cleanup on unmount).

## Development Workflow

1. **Research:** Map the codebase and verify assumptions using `grep_search` and `read_file`.
2. **Strategy:** Formulate a plan and share a concise summary.
3. **Execution:**
   - **Plan:** Define implementation and testing strategy.
   - **Act:** Apply surgical changes. Use `replace` for large files.
   - **Validate:** Run `make test-backend` and `make test-frontend`. **All tests must pass before commit.**
4. **Documentation:** Update relevant `.md` files when changing architecture or adding features.

## Conventions

- **Python:** PEP 8 (100 chars), type hints, Google-style docstrings. Black/Ruff/Mypy.
- **TypeScript:** 2 spaces, single quotes, explicit types. ESLint/Vitest.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `perf:`, `refactor:`).

## Security (MANDATORY)

- **Parameterized Queries:** Never use f-strings for Cypher/SQL. Use `%(name)s` with psycopg.
- **Identifier Validation:** Always use `validate_graph_name` or `validate_label_name` for dynamic identifiers.
- **Headers:** `SecurityHeadersMiddleware` provides HSTS, CSP (nosniff, frame-ancestors, etc.).
- **Audit Logging:** Security events (CSRF failures, rate limits) are logged with `SECURITY:` prefix and extra context.
- **Secrets:** Credentials encrypted at rest (AES-256-GCM). No secrets in repo.

## API & Documentation

- Base: `/api/v1`. Full specs in `docs/ARCHITECTURE.md`.
- **Setup:** `docs/QUICKSTART.md`.
- **Advanced:** `docs/ADVANCED_FEATURES.md`.
- **Troubleshooting:** `docs/TROUBLESHOOTING.md`.
- **Engineering backlog:** `docs/BACKLOG.md` (prioritized follow-ups).
