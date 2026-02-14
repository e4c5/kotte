# Architecture Overview

## System Components

### Backend (FastAPI)

The backend is a FastAPI application that provides a REST API for graph operations.

**Core Modules:**
- `app/core/` - Core functionality (config, errors, auth, database)
- `app/api/v1/` - API route handlers
- `app/models/` - Pydantic models for request/response validation
- `app/services/` - Business logic (to be implemented)

**Key Features:**
- Session-based authentication with secure cookies
- Database connection management per session
- Structured error handling with stable error codes
- Parameterized query execution for security

### Frontend (React + TypeScript)

The frontend is a React application built with Vite.

**Core Modules:**
- `src/services/` - API client and service layer
- `src/stores/` - State management (Zustand)
- `src/components/` - React components
- `src/pages/` - Page components

**Key Features:**
- Type-safe API client with error handling
- State management with Zustand
- Routing with React Router

## API Contract

All API endpoints follow RESTful conventions and return structured error responses.

Base path: `/api/v1`

### Authentication

All protected endpoints require a valid session cookie. Sessions are created via `/session/connect` and invalidated via `/session/disconnect`.

### Error Responses

All errors follow this structure:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "category": "category",
    "message": "Human-readable message",
    "details": {},
    "request_id": "uuid",
    "timestamp": "ISO-8601",
    "retryable": false
  }
}
```

## Security

- All database queries use parameterization
- Session cookies are HttpOnly and Secure (in production)
- Credentials are never returned in API responses
- Graph names and queries are validated before execution

## Data Flow

1. User connects via frontend → Backend creates session and DB connection
2. User executes query → Backend validates, executes, returns results
3. Results are parsed from AGE agtype format
4. Frontend renders graph or table view

## Future Enhancements

- Query cancellation implementation
- CSV import with async job system
- D3.js graph visualization
- Advanced filtering and styling
- Property discovery for metadata

