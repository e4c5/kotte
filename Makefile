.PHONY: help install-backend install-frontend install-hooks dev-backend dev-frontend test-backend test-frontend lint-backend lint-frontend \
	format-backend precommit-run \
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
