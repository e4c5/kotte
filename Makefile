.PHONY: help install-backend install-frontend install-hooks dev-backend dev-frontend test-backend test-frontend lint-backend lint-frontend \
	format-backend precommit-run \
	migrate-up migrate-down migrate-current migrate-history migrate-new reindex-labels \
	compose-up-dev compose-up-prod compose-down-dev compose-down-prod compose-logs-dev compose-logs-prod compose-build-prod

help:
	@echo "Available targets:"
	@echo "  install-backend    - Install backend dependencies"
	@echo "  install-frontend    - Install frontend dependencies"
	@echo "  dev-backend         - Run backend development server"
	@echo "  dev-frontend        - Run frontend development server"
	@echo "  test-backend        - Run backend tests"
	@echo "  test-frontend       - Run frontend tests once (vitest run, with timeout)"
	@echo "  lint-backend        - Lint backend code"
	@echo "  lint-frontend       - Lint frontend code"
	@echo "  format-backend      - Run black across backend/app + tests"
	@echo ""
	@echo "Pre-commit (ROADMAP B8):"
	@echo "  install-hooks       - Install the local git pre-commit hook"
	@echo "  precommit-run       - Run every hook against every tracked file"
	@echo ""
	@echo "Migrations (ROADMAP B7 — target DB via DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD):"
	@echo "  migrate-up          - Apply all pending migrations (alembic upgrade head)"
	@echo "  migrate-down        - Revert the most recent migration (alembic downgrade -1)"
	@echo "  migrate-current     - Show the head revision applied to the target DB"
	@echo "  migrate-history     - Show the migration chain"
	@echo "  migrate-new         - Scaffold a new migration; pass MSG='short description'"
	@echo "  reindex-labels      - Walk ag_catalog and create id/start_id/end_id indices on every label"
	@echo ""
	@echo "Docker Compose:"
	@echo "  compose-up-dev      - Start the dev stack (source mounts, --reload, vite HMR)"
	@echo "  compose-down-dev    - Stop the dev stack"
	@echo "  compose-logs-dev    - Tail logs from the dev stack"
	@echo "  compose-up-prod     - Start the prod stack (nginx frontend, hardened, env_file)"
	@echo "  compose-down-prod   - Stop the prod stack"
	@echo "  compose-logs-prod   - Tail logs from the prod stack"
	@echo "  compose-build-prod  - Rebuild prod images without starting"

install-backend:
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

# Assumes backend/venv exists (via `install-backend`); pre-commit is in
# requirements-dev.txt so no extra install step is needed.
install-hooks:
	cd backend && . venv/bin/activate && cd .. && pre-commit install

precommit-run:
	cd backend && . venv/bin/activate && cd .. && pre-commit run --all-files

format-backend:
	cd backend && . venv/bin/activate && black app tests

# Migrations (ROADMAP B7). Alembic is operator tooling: it targets a
# user-supplied AGE database via DB_* env vars (the same ones
# `scripts/migrate_add_indices.py` already uses). Override the URL
# entirely with ALEMBIC_SQLALCHEMY_URL or `alembic -x url=...`.

migrate-up:
	cd backend && . venv/bin/activate && alembic upgrade head

migrate-down:
	cd backend && . venv/bin/activate && alembic downgrade -1

migrate-current:
	cd backend && . venv/bin/activate && alembic current

migrate-history:
	cd backend && . venv/bin/activate && alembic history --verbose

# Usage: `make migrate-new MSG="add something"`. Autogenerate is
# deliberately off — we don't ship SQLAlchemy models, so every
# migration is hand-written raw SQL via `op.execute(...)`.
migrate-new:
	@test -n "$(MSG)" || { echo "Usage: make migrate-new MSG=\"short description\""; exit 1; }
	cd backend && . venv/bin/activate && alembic revision -m "$(MSG)"

# Complement to `migrate-up`: label indices depend on the current
# catalog contents (which labels exist in which graphs), so they can't
# be captured as a static migration. Re-run any time you add/drop
# labels and want ag_catalog.ag_label's id/start_id/end_id columns
# reindexed.
reindex-labels:
	cd backend && . venv/bin/activate && python -m scripts.migrate_add_indices

dev-backend:
	cd backend && . venv/bin/activate && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test-backend:
	cd backend && . venv/bin/activate && pytest

# Single run + wall-clock cap so CI/agents do not hang on watch mode or stuck workers.
# Override: make test-frontend TEST_TIMEOUT=600s
TEST_TIMEOUT ?= 180s
test-frontend:
	cd frontend && timeout $(TEST_TIMEOUT) npm run test:run

lint-backend:
	cd backend && . venv/bin/activate && ruff check . && black --check . && mypy app

lint-frontend:
	cd frontend && npm run lint

# ---------------------------------------------------------------------------
# Docker Compose targets (ROADMAP B6)
#
# Dev uses docker-compose.dev.yml (source mounts, uvicorn --reload, vite
# HMR). Prod uses docker-compose.prod.yml + deployment/.env.prod (nginx
# frontend, resource limits, secrets from the env_file). The two stacks
# share named volumes (`age-data`, `backend-data`) so switching between
# them preserves AGE data and saved credentials.
# ---------------------------------------------------------------------------

COMPOSE_DEV  := docker compose -f deployment/docker-compose.dev.yml
COMPOSE_PROD := docker compose -f deployment/docker-compose.prod.yml --env-file deployment/.env.prod

compose-up-dev:
	$(COMPOSE_DEV) up -d

compose-down-dev:
	$(COMPOSE_DEV) down

compose-logs-dev:
	$(COMPOSE_DEV) logs -f

compose-up-prod:
	@test -f deployment/.env.prod || { echo "deployment/.env.prod not found — copy deployment/.env.prod.example to deployment/.env.prod and fill in real values"; exit 1; }
	$(COMPOSE_PROD) up -d

compose-down-prod:
	$(COMPOSE_PROD) down

compose-logs-prod:
	$(COMPOSE_PROD) logs -f

compose-build-prod:
	@test -f deployment/.env.prod || { echo "deployment/.env.prod not found — copy deployment/.env.prod.example to deployment/.env.prod and fill in real values"; exit 1; }
	$(COMPOSE_PROD) build
