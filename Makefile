.PHONY: help install-backend install-frontend dev-backend dev-frontend test-backend test-frontend lint-backend lint-frontend

help:
	@echo "Available targets:"
	@echo "  install-backend    - Install backend dependencies"
	@echo "  install-frontend    - Install frontend dependencies"
	@echo "  dev-backend         - Run backend development server"
	@echo "  dev-frontend        - Run frontend development server"
	@echo "  test-backend        - Run backend tests"
	@echo "  test-frontend       - Run frontend tests"
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

test-frontend:
	cd frontend && npm test

lint-backend:
	cd backend && . venv/bin/activate && ruff check . && black --check . && mypy app

lint-frontend:
	cd frontend && npm run lint

