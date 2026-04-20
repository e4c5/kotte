# Contributing to Kotte

Thank you for your interest in contributing to Kotte! This guide will help you get started with development, understand the codebase, and make meaningful contributions.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Architecture Overview](#architecture-overview)
5. [Development Workflow](#development-workflow)
6. [Coding Standards](#coding-standards)
7. [Testing Guidelines](#testing-guidelines)
8. [Security Considerations](#security-considerations)
9. [Pull Request Process](#pull-request-process)
10. [Common Tasks](#common-tasks)

---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** - Backend development
- **Node.js 18+** - Frontend development
- **PostgreSQL 14+** - Database for testing
- **Apache AGE Extension** - Graph database functionality
- **Git** - Version control
- **Docker** (optional) - For consistent development environment

### Quick Start

1. **Fork the Repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/kotte.git
   cd kotte
   ```

2. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set Up Development Environment**
   ```bash
   make install-backend
   make install-frontend
   make install-hooks       # wires black + ruff + eslint + hygiene hooks into `git commit`
   ```

   The pre-commit hooks mirror the CI lint gates (black, ruff,
   trailing-whitespace, EOF newline, JSON/YAML/TOML parsing, frontend
   eslint) so formatting / lint regressions are caught locally instead
   of in CI. Run `make precommit-run` to verify the whole tree at any
   time.

4. **Start Development Servers**
   ```bash
   # Terminal 1
   make dev-backend

   # Terminal 2
   make dev-frontend
   ```

---

## Development Setup

### Backend Setup

The backend is a FastAPI application written in Python.

#### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 2. Install Dependencies

```bash
# Development dependencies (includes testing, linting)
pip install -r requirements.txt -r requirements-dev.txt
```

#### 3. Configure Environment

Create a `.env` file in the `backend/` directory:

```env
# Development settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
STRUCTURED_LOGGING=false # Set to true for JSON logs

# Database defaults (users connect via UI)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres

# Session security (generate with: openssl rand -urlsafe 32)
SESSION_SECRET_KEY=your-secret-key-here

# Optional: Credential storage
CREDENTIAL_STORAGE_TYPE=json_file
CREDENTIAL_STORAGE_PATH=./data/connections.json
MASTER_ENCRYPTION_KEY=your-master-key-here
```

### Frontend Setup

The frontend is a React application built with Vite and TypeScript.

#### 1. Install Dependencies

```bash
cd frontend
npm install
```

#### 2. Run Frontend

```bash
npm run dev
```

---

## Project Structure

```
kotte/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/             # API endpoints (session, graph, query, etc.)
│   │   ├── core/               # Core system logic
│   │   │   ├── database/       # Modular DB: connection, cypher, manager
│   │   │   ├── auth.py         # Session & Auth
│   │   │   ├── logging.py      # Structured logging
│   │   │   ├── metrics.py      # Prometheus metrics
│   │   │   └── middleware.py   # CSRF, Security Headers, Rate limiting
│   │   ├── models/             # Pydantic request/response schemas
│   │   ├── services/           # Business logic (agtype, metadata, cache)
│   │   └── main.py             # App entry & middleware registration
│   └── tests/                  # Pytest suite
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/         # React UI components
│   │   │   └── GraphControls/  # Modular control tabs (Layout, Filter, Style)
│   │   ├── hooks/              # Custom React hooks (export, cache)
│   │   ├── pages/              # Lazy-loaded route components
│   │   ├── services/           # API clients with caching
│   │   ├── stores/             # Zustand state management
│   │   └── utils/              # Graph helpers and API cache
│   └── tests/                  # Vitest suite
```

---

## Development Workflow

### Making Changes

1. **Verify Assumptions**: Use `grep_search` and `read_file` to understand existing patterns.
2. **Implement Feature**: Follow existing architectural patterns (modular DB, decomposed components).
3. **Write Tests**: Add unit tests for logic and integration tests for endpoints.
4. **Validate**: Run full test suites before committing.

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test -- --run
```

---

## Coding Standards

- **Python**: PEP 8, Type Hints, Google-style docstrings. Formatting is
  enforced by `black` (line-length 100, target-version py311 — see
  `[tool.black]` in `backend/pyproject.toml`) and linted by `ruff`. Both
  run via the `make install-hooks` pre-commit hook and the backend CI
  workflow. Run `make format-backend` to reformat manually.
- **TypeScript**: 2 spaces, single quotes, explicit types, functional components.
- **Security**: Never use f-strings for queries. Use `%(name)s`. Validate all identifiers.

---

## Testing Guidelines

### Backend (Pytest)

We use `pytest` with `pytest-asyncio` and `pytest-cov`.

- **Unit Tests**: Test logic in `app/services` or `app/core/database/utils.py`.
- **Integration Tests**: Test endpoints in `app/api/v1`. Use the `mock_db_connection` fixture.
- **Coverage**: Aim for 80% coverage on new code.

### Frontend (Vitest)

We use `vitest` with `react-testing-library` and `jsdom`.

- **Global Mode**: `globals: true` is enabled in `vite.config.ts` for automatic cleanup.
- **D3 Mocking**: Components using D3 require a robust mock of simulations and selections. See `GraphView.test.tsx` for examples.
- **Lazy Loading**: Ensure tests handle `Suspense` if testing components that use `lazy()`.

---

## Security Considerations

- **Security Headers**: Managed by `SecurityHeadersMiddleware`.
- **Audit Logging**: Use `logger.warning("SECURITY: ...")` for sensitive failures.
- **CSRF**: Tokens required for all POST/PUT/PATCH/DELETE requests.
- **Rate Limiting**: Applied per-IP and per-session.

---

## Pull Request Process

1. **Tests Pass**: `make test-backend` and `make test-frontend` must pass.
2. **Lint Pass**: `make lint-backend` and `make lint-frontend` must pass.
3. **Docs Updated**: Update `AGENTS.md`, `ARCHITECTURE.md`, or `PERFORMANCE.md` as needed.
4. **Commits**: Use Conventional Commits format.
