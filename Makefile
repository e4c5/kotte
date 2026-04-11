.PHONY: help install-backend install-frontend dev-backend dev-frontend test-backend test-frontend lint-backend lint-frontend

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

install-backend:
	cd backend && python3 -m venv venv && . venv/bin/activate && pip install -r requirements-dev.txt

install-frontend:
	cd frontend && npm install

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

