# Kotte - Apache AGE Visualizer

A clean-room implementation of an Apache AGE graph visualizer with a FastAPI backend and React frontend.

## Status

🚧 **In Development** - Core infrastructure is in place. See [Implementation Status](#implementation-status) below.

## Architecture

- **Backend**: FastAPI application providing REST API for database connectivity, query execution, and graph operations
- **Frontend**: React + TypeScript application (D3.js visualization coming soon)

## Quick Start

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed setup instructions.

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Or use the Makefile:

```bash
make install-backend install-frontend
make dev-backend    # Terminal 1
make dev-frontend   # Terminal 2
```

## Project Structure

```
kotte/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API routes (session, graph, query)
│   │   ├── core/     # Core services (auth, db, errors, config)
│   │   ├── models/   # Pydantic models
│   │   └── services/ # Business logic (to be implemented)
│   └── tests/        # Backend tests
├── frontend/         # React frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── pages/       # Page components
│   │   ├── services/    # API client
│   │   └── stores/      # State management (Zustand)
│   └── tests/        # Frontend tests
└── docs/             # Documentation
```

## Implementation Status

### ✅ Completed

- **Backend Core**: FastAPI app, error handling, middleware, configuration
- **Authentication**: Session management with secure cookies
- **Database**: Connection management, AGE integration, parameterized queries
- **API Endpoints**: Session, graph metadata, query execution, CSV import
- **Services**: AgType parsing, graph element extraction, metadata discovery
- **Frontend Core**: React + TypeScript + Vite setup, routing, state management
- **UI Components**: Connection page, query editor, graph view (D3.js), table view, metadata sidebar
- **Features**: Query execution, graph/table toggle, query history, export, metadata templates

### 🚧 Partially Implemented

- Query cancellation (endpoint exists, needs PostgreSQL integration)
- CSV import (basic sync implementation, needs async jobs)
- Meta-graph discovery (basic implementation)

### 📋 Remaining

- Graph interactions (filtering, styling, layout switching, expansion)
- CSV import UI with progress tracking
- Settings & persistence (theme, preferences)
- Comprehensive testing (unit, integration, E2E)
- Security hardening (audit logging, rate limiting)

See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for detailed status.

## Security

- ✅ Authentication required for all protected endpoints
- ✅ Parameterized queries (no SQL injection)
- ✅ Secrets from environment variables only
- ✅ Session security with HttpOnly cookies
- ✅ Safe mode for read-only queries (configurable)
- 🚧 Audit logging (to be implemented)
- 🚧 Rate limiting (to be implemented)

## API Documentation

When running the backend, API documentation is available at:
- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## Testing

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm test
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture details.

## Contributing

This is a clean-room implementation. See the requirements document for detailed specifications.

## License

[To be determined]
