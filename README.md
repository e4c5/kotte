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

- Backend core infrastructure (FastAPI, error handling, middleware)
- Authentication and session management
- Database connection management
- Basic API endpoints (connect, disconnect, status, list graphs, metadata)
- Query execution endpoint (basic implementation)
- Frontend project structure (React + TypeScript + Vite)
- Frontend API client and state management
- Connection UI
- Basic workspace page

### 🚧 In Progress / TODO

- **Query Execution**: agtype parsing, result transformation
- **Graph Visualization**: D3.js implementation with force layout
- **Query Editor**: Cypher editor with history and shortcuts
- **Table View**: Pagination and virtualization
- **Graph Interactions**: Filtering, layout switching, styling
- **Metadata Sidebar**: Graph explorer, query templates
- **CSV Import**: Async job system with progress tracking
- **Testing**: Comprehensive unit and integration tests
- **Security Hardening**: Complete security checklist validation

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
