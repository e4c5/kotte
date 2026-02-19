# Architecture Overview

Kotte is a web-based graph visualizer for Apache AGE, built with a FastAPI backend and React frontend. This document provides a comprehensive overview of the system architecture, component interactions, and design decisions.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Backend Architecture](#backend-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Data Flow](#data-flow)
5. [Security Architecture](#security-architecture)
6. [API Reference](#api-reference)
7. [Database Integration](#database-integration)
8. [Deployment Architecture](#deployment-architecture)

---

## System Architecture

### High-Level Overview

```
┌─────────────┐         ┌─────────────┐         ┌──────────────────┐
│   Browser   │────────▶│   FastAPI   │────────▶│   PostgreSQL     │
│  (React)    │◀────────│   Backend   │◀────────│   + Apache AGE   │
└─────────────┘         └─────────────┘         └──────────────────┘
     │                         │
     │                         ▼
     │                  ┌─────────────┐
     │                  │  Encrypted  │
     │                  │  Credential │
     │                  │   Storage   │
     └──────────────────┴─────────────┘
        Session Cookies
```

### Component Responsibilities

| Component | Responsibilities |
|-----------|------------------|
| **React Frontend** | UI rendering, user interaction, state management, visualization |
| **FastAPI Backend** | API routing, authentication, query execution, credential management |
| **PostgreSQL + AGE** | Graph data storage, Cypher query execution, metadata management |
| **Credential Storage** | Encrypted storage of saved database connections |

---

## Backend Architecture

### Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database Driver**: psycopg (async PostgreSQL driver)
- **Validation**: Pydantic v2
- **Security**: cryptography library for AES-256-GCM
- **Session**: In-memory session storage with secure cookies

### Directory Structure

```
backend/app/
├── api/v1/              # API endpoints
│   ├── session.py       # Session management (connect/disconnect)
│   ├── graph.py         # Graph operations (list, metadata, meta-graph)
│   ├── query.py         # Query execution and cancellation
│   ├── import_csv.py    # CSV import endpoints
│   └── health.py        # Health check endpoints
├── core/                # Core functionality
│   ├── auth.py          # Session authentication
│   ├── config.py        # Configuration management
│   ├── database.py      # Database connection management
│   ├── errors.py        # Error handling and definitions
│   ├── middleware.py    # CORS, rate limiting, request ID
│   └── security.py      # Security utilities (CSRF, encryption)
├── models/              # Pydantic models
│   ├── session.py       # Session request/response models
│   ├── graph.py         # Graph data models
│   ├── query.py         # Query request/response models
│   └── errors.py        # Error response models
├── services/            # Business logic
│   ├── agtype.py        # Apache AGE type parsing
│   ├── metadata.py      # Graph metadata discovery
│   └── connection_storage.py  # Encrypted credential storage
└── main.py              # Application entry point
```

### Core Modules

#### Session Management (`app/core/auth.py`)

Handles user sessions with secure cookies:

- **Session Creation**: On database connection
- **Session Storage**: In-memory dictionary (key: session_id, value: session data)
- **Session Timeout**: 1 hour maximum, 30 minutes idle timeout
- **Session Security**: HttpOnly, SameSite=Lax, Secure (in production)

**⚠️ Production Warning**: In-memory session storage is **not suitable for production** when running multiple backend instances. For production deployments:
- Use Redis, Memcached, or database-backed session storage
- Configure session store in `app/core/auth.py`
- Ensure session store is accessible by all backend instances
- Consider session replication for high availability

See [Contributing Guide](CONTRIBUTING.md#session-storage-production) for Redis configuration examples.

#### Database Connection (`app/core/database.py`)

Manages PostgreSQL connections per session:

- **Connection Pool**: One connection per active session
- **AGE Verification**: Ensures AGE extension is loaded
- **Search Path**: Sets `ag_catalog` for AGE functions
- **Connection Cleanup**: Closes connections on session disconnect

#### Error Handling (`app/core/errors.py`)

Structured error responses with stable error codes:

```python
class ErrorResponse:
    code: str              # Stable error code (e.g., "DB_UNAVAILABLE")
    category: str          # Error category (e.g., "database")
    message: str           # Human-readable message
    details: dict          # Additional context
    request_id: str        # Request correlation ID
    timestamp: datetime    # Error timestamp
    retryable: bool        # Whether retry might succeed
```

**Error Categories:**
- `database` - Database connection/query errors
- `validation` - Input validation errors
- `authentication` - Auth/session errors
- `not_found` - Resource not found errors
- `server` - Internal server errors

#### Security (`app/core/security.py`)

Security utilities and middleware:

- **CSRF Protection**: Token-based CSRF protection
- **Rate Limiting**: Per-IP and per-user rate limits
- **Input Validation**: Strict validation on all inputs
- **Credential Encryption**: AES-256-GCM for stored credentials

### Services

#### AGE Type Parser (`app/services/agtype.py`)

Parses Apache AGE's custom `agtype` JSON format:

**Supported Types:**
- Vertices (nodes with id, label, properties)
- Edges (relationships with id, label, start_id, end_id, properties)
- Paths (sequences of vertices and edges)
- Scalars (numbers, strings, booleans, null)
- Arrays and objects (nested structures)

**BigInt Handling:**
- Converts 64-bit integers to strings
- Prevents JavaScript Number precision loss

#### Metadata Service (`app/services/metadata.py`)

Discovers graph metadata:

**Discovery Methods:**
- **Labels**: Query `ag_catalog.ag_label` for all node/edge labels
- **Counts**: Use PostgreSQL table statistics for approximate counts
- **Properties**: Sample nodes/edges to discover property schemas
- **Meta-graph**: Analyze relationships between label types

---

## Frontend Architecture

### Technology Stack

- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **State Management**: Zustand
- **Routing**: React Router v6
- **Visualization**: D3.js v7
- **HTTP Client**: Axios

### Directory Structure

```
frontend/src/
├── components/          # Reusable components
│   ├── GraphView.tsx           # D3.js graph visualization
│   ├── TableView.tsx           # Table results view
│   ├── QueryEditor.tsx         # Cypher query editor
│   ├── GraphControls.tsx       # Layout and styling controls
│   ├── MetadataSidebar.tsx     # Graph metadata explorer
│   └── ErrorBoundary.tsx       # Error handling wrapper
├── pages/               # Page components
│   ├── ConnectionPage.tsx      # Database connection UI
│   └── WorkspacePage.tsx       # Main workspace with query/viz
├── services/            # API client
│   ├── api.ts                  # Base API client with error handling
│   ├── session.ts              # Session API (connect/disconnect)
│   ├── graph.ts                # Graph API (list, metadata)
│   └── query.ts                # Query API (execute, cancel)
├── stores/              # Zustand state stores
│   ├── sessionStore.ts         # Session state (connection, user)
│   ├── graphStore.ts           # Graph state (selected graph, metadata)
│   └── queryStore.ts           # Query state (query, results, history)
├── types/               # TypeScript type definitions
│   ├── graph.ts                # Graph data types
│   ├── query.ts                # Query types
│   └── api.ts                  # API response types
└── App.tsx              # Root component with routing
```

### State Management

Zustand stores manage application state:

#### Session Store
```typescript
interface SessionState {
  isConnected: boolean;
  connectionInfo: ConnectionInfo | null;
  savedConnections: SavedConnection[];
  connect: (config: ConnectionConfig) => Promise<void>;
  disconnect: () => Promise<void>;
}
```

#### Graph Store
```typescript
interface GraphState {
  graphs: Graph[];
  selectedGraph: string | null;
  metadata: GraphMetadata | null;
  selectGraph: (name: string) => Promise<void>;
  loadMetadata: () => Promise<void>;
}
```

#### Query Store
```typescript
interface QueryState {
  query: string;
  parameters: Record<string, unknown>;
  results: QueryResult | null;
  history: string[];
  isExecuting: boolean;
  execute: () => Promise<void>;
  cancel: () => Promise<void>;
}
```

### Visualization Component

The `GraphView` component uses D3.js for interactive graph visualization:

**Features:**
- Force-directed layout (default)
- Alternative layouts: hierarchical, radial, grid, random
- Zoom and pan with d3-zoom
- Node selection and pinning
- Automatic node coloring by label
- Edge arrows and labels

**Performance Optimization:**
- Canvas rendering for large graphs (>1000 nodes)
- SVG rendering for smaller graphs
- Visualization caps: max 5000 nodes, 10000 edges
- Auto-switch to table view when exceeds limits

---

## Data Flow

### Sequence Diagrams

#### 1. User Authentication & Connection

```
User          Frontend        Backend         PostgreSQL
 │                │              │                 │
 │   Enter creds  │              │                 │
 ├───────────────▶│              │                 │
 │                │ POST /session/connect         │
 │                ├─────────────▶│                 │
 │                │              │  Test connection│
 │                │              ├────────────────▶│
 │                │              │◀────────────────┤
 │                │              │  Verify AGE     │
 │                │              ├────────────────▶│
 │                │              │◀────────────────┤
 │                │              │                 │
 │                │ Session cookie + graphs list  │
 │                │◀─────────────┤                 │
 │  Connected!    │              │                 │
 │◀───────────────┤              │                 │
```

**Steps:**
1. User enters database credentials in connection form
2. Frontend sends POST to `/api/v1/session/connect`
3. Backend creates database connection
4. Backend verifies AGE extension is available
5. Backend creates session and sets secure cookie
6. Backend returns list of available graphs
7. Frontend updates state and navigates to workspace

#### 2. Query Execution

```
User       Frontend     Backend      PostgreSQL    AGE Parser
 │            │            │              │             │
 │ Enter query│            │              │             │
 ├───────────▶│            │              │             │
 │ Click Run  │            │              │             │
 ├───────────▶│ POST /queries/execute    │             │
 │            ├───────────▶│              │             │
 │            │            │ Validate query            │
 │            │            │──────────────┐            │
 │            │            │◀─────────────┘            │
 │            │            │              │             │
 │            │            │ SELECT * FROM cypher(...)│
 │            │            ├─────────────▶│            │
 │            │            │              │ Execute    │
 │            │            │              ├───────────▶│
 │            │            │              │ Return agtype
 │            │            │              │◀───────────┤
 │            │            │ Parse agtype │            │
 │            │            ├─────────────────────────▶ │
 │            │            │◀────────────────────────── │
 │            │            │              │             │
 │            │ Results (nodes/edges)    │             │
 │            │◀───────────┤              │             │
 │ Display viz│            │              │             │
 │◀───────────┤            │              │             │
```

**Steps:**
1. User writes Cypher query and clicks "Run"
2. Frontend sends POST to `/api/v1/queries/execute`
3. Backend validates query and parameters
4. Backend executes Cypher via `cypher()` function
5. PostgreSQL + AGE execute query and return agtype results
6. Backend parses agtype to extract nodes, edges, paths, scalars
7. Backend returns structured results to frontend
8. Frontend renders results in graph or table view

#### 3. Metadata Discovery

```
User       Frontend     Backend      PostgreSQL
 │            │            │              │
 │ Select graph│           │              │
 ├───────────▶│            │              │
 │            │ GET /graphs/{name}/metadata
 │            ├───────────▶│              │
 │            │            │ Query ag_label
 │            │            ├─────────────▶│
 │            │            │◀─────────────┤
 │            │            │ Get counts   │
 │            │            ├─────────────▶│
 │            │            │◀─────────────┤
 │            │            │ Sample properties
 │            │            ├─────────────▶│
 │            │            │◀─────────────┤
 │            │ Metadata (labels, counts, props)
 │            │◀───────────┤              │
 │ Show sidebar│           │              │
 │◀───────────┤            │              │
```

**Steps:**
1. User selects a graph from sidebar
2. Frontend requests metadata: GET `/api/v1/graphs/{name}/metadata`
3. Backend queries `ag_catalog.ag_label` for all labels
4. Backend gets approximate counts from table statistics
5. Backend samples nodes/edges to discover properties
6. Backend returns comprehensive metadata
7. Frontend displays in metadata sidebar

---

## Security Architecture

### Session Security

**Session Cookie Configuration:**
```python
session_cookie = {
    "name": "kotte_session",
    "httponly": True,        # No JavaScript access
    "samesite": "lax",       # CSRF protection
    "secure": True,          # HTTPS only (production)
    "max_age": 3600,         # 1 hour
}
```

**Session Data:**
- Session ID (UUID)
- Connection configuration (encrypted)
- Database connection object
- Last activity timestamp

**Session Timeout:**
- Maximum lifetime: 1 hour
- Idle timeout: 30 minutes
- Auto-renewal on activity

### Credential Encryption

Saved database connections use AES-256-GCM encryption:

**Encryption Process:**
1. User saves connection with password
2. Generate unique salt for this credential
3. Derive encryption key: PBKDF2(master_key, salt, 100k iterations)
4. Encrypt password: AES-256-GCM(key, password)
5. Store: {salt, nonce, ciphertext} in JSON file

**Decryption Process:**
1. User selects saved connection
2. Read {salt, nonce, ciphertext} from storage
3. Derive key: PBKDF2(master_key, salt, 100k iterations)
4. Decrypt: AES-256-GCM-decrypt(key, nonce, ciphertext)
5. Use plaintext password for connection

**Key Management:**
- **Development**: Auto-generate and persist to `.master_encryption_key`
- **Production**: Must set `MASTER_ENCRYPTION_KEY` environment variable
- **Rotation**: Support for periodic key rotation

### SQL Injection Prevention

**Parameterized Queries:**
```python
# ✅ SAFE - Parameterized
query = "SELECT * FROM cypher($1, $2) AS (result agtype)"
await conn.execute(query, graph_name, cypher_query)

# ❌ UNSAFE - String interpolation
query = f"SELECT * FROM cypher('{graph_name}', '{cypher_query}')"
await conn.execute(query)
```

**Identifier Validation:**
```python
def validate_identifier(name: str) -> bool:
    """Validate PostgreSQL identifier (graph name, label, etc.)."""
    # Must start with letter or underscore
    # Can contain letters, digits, underscores
    # Max 63 characters
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$', name))
```

### CSRF Protection

- CSRF tokens for state-changing requests
- SameSite=Lax cookie attribute
- Origin header verification

### Rate Limiting

```python
# Per-IP rate limiting
@limiter.limit("60/minute")
async def execute_query(...):
    pass

# Per-user rate limiting
@limiter.limit("100/minute", key_func=get_user_id)
async def execute_query(...):
    pass
```

---

## API Reference

### Base URL

`http://localhost:8000/api/v1`

### Session Endpoints

#### POST /session/connect

Create session and connect to database.

**Request:**
```json
{
  "host": "localhost",
  "port": 5432,
  "database": "postgres",
  "user": "postgres",
  "password": "password",
  "save": false,
  "connection_name": "My Connection"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "graphs": ["graph1", "graph2"],
  "message": "Connected successfully"
}
```

#### POST /session/disconnect

Disconnect and invalidate session.

**Response:**
```json
{
  "message": "Disconnected successfully"
}
```

### Graph Endpoints

#### GET /graphs

List all graphs in connected database.

**Response:**
```json
{
  "graphs": [
    {"name": "graph1", "node_count": 1000, "edge_count": 5000},
    {"name": "graph2", "node_count": 500, "edge_count": 2000}
  ]
}
```

#### GET /graphs/{name}/metadata

Get detailed metadata for a graph.

**Response:**
```json
{
  "name": "graph1",
  "node_labels": [
    {
      "name": "Person",
      "count": 500,
      "properties": ["name", "age", "email"]
    }
  ],
  "edge_types": [
    {
      "name": "KNOWS",
      "count": 2000,
      "properties": ["since", "strength"]
    }
  ]
}
```

### Query Endpoints

#### POST /queries/execute

Execute Cypher query.

**Request:**
```json
{
  "graph": "graph1",
  "query": "MATCH (n:Person) WHERE n.age > $minAge RETURN n LIMIT $limit",
  "parameters": {
    "minAge": 25,
    "limit": 10
  }
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "results": {
    "nodes": [...],
    "edges": [...],
    "raw_rows": [...]
  },
  "execution_time_ms": 42
}
```

#### POST /queries/{request_id}/cancel

Cancel running query (implemented).

Uses PostgreSQL `pg_cancel_backend()` to terminate the query at the database level.

**Response (Success):**
```json
{
  "cancelled": true,
  "request_id": "uuid"
}
```

**Error Responses:**

**400 Bad Request** - Invalid request:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "category": "validation",
    "message": "Invalid request ID format",
    "details": {},
    "request_id": "uuid",
    "timestamp": "2026-02-19T01:00:00Z",
    "retryable": false
  }
}
```

**401 Unauthorized** - Not authenticated:
```json
{
  "error": {
    "code": "AUTH_REQUIRED",
    "category": "authentication",
    "message": "Authentication required",
    "details": {},
    "request_id": "uuid",
    "timestamp": "2026-02-19T01:00:00Z",
    "retryable": false
  }
}
```

**429 Too Many Requests** - Rate limit exceeded:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "category": "rate_limit",
    "message": "Rate limit exceeded. Please try again later.",
    "details": {"retry_after": 60},
    "request_id": "uuid",
    "timestamp": "2026-02-19T01:00:00Z",
    "retryable": true
  }
}
```

**500 Internal Server Error** - Server error:
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "category": "server",
    "message": "An unexpected error occurred",
    "details": {},
    "request_id": "uuid",
    "timestamp": "2026-02-19T01:00:00Z",
    "retryable": true
  }
}
```

---

## Database Integration

### Apache AGE Integration

**Extension Loading:**
```sql
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
```

**Query Execution:**
```sql
SELECT * FROM cypher('graph_name', $$
  MATCH (n:Person)-[r:KNOWS]->(m:Person)
  WHERE n.age > 25
  RETURN n, r, m
  LIMIT 10
$$) AS (n agtype, r agtype, m agtype);
```

**AGType Format:**

Vertices:
```json
{
  "id": 844424930131969,
  "label": "Person",
  "properties": {
    "name": "Alice",
    "age": 30
  }
}
```

Edges:
```json
{
  "id": 1125899906842625,
  "label": "KNOWS",
  "start_id": 844424930131969,
  "end_id": 844424930131970,
  "properties": {
    "since": 2020
  }
}
```

---

## Deployment Architecture

### Development

```
Frontend (Vite Dev Server)     Backend (uvicorn --reload)
http://localhost:5173          http://localhost:8000
         │                              │
         └──────────────┬───────────────┘
                        │
                   PostgreSQL
                localhost:5432
```

### Production

```
┌──────────────────────────────────────────┐
│           Nginx (Reverse Proxy)          │
│          https://kotte.example.com       │
└────────┬─────────────────────┬───────────┘
         │                     │
    ┌────▼─────┐         ┌────▼─────┐
    │ Frontend │         │ Backend  │
    │ (Static) │         │ (Gunicorn│
    │          │         │ +uvicorn)│
    └──────────┘         └────┬─────┘
                              │
                         ┌────▼─────────┐
                         │  PostgreSQL  │
                         │  + AGE       │
                         │  (managed)   │
                         └──────────────┘
```

**Nginx Configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name kotte.example.com;

    # Frontend static files
    location / {
        root /var/www/kotte/frontend;
        try_files $uri /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Environment Variables

**Backend:**
```env
# Production settings
ENVIRONMENT=production
DEBUG=false
SESSION_SECRET_KEY=<generated-secret>
MASTER_ENCRYPTION_KEY=<from-secret-manager>

# Database
DB_HOST=db.example.com
DB_PORT=5432

# Security
CORS_ORIGINS=https://kotte.example.com
RATE_LIMIT_ENABLED=true

# Limits
QUERY_TIMEOUT=300
MAX_NODES_FOR_GRAPH=5000
```

**Frontend:**
```env
VITE_API_BASE_URL=https://kotte.example.com
```

---

## Performance Considerations

### Query Optimization

- Query timeout: 5 minutes default
- Result size limits: 100,000 rows max
- Visualization limits: 5,000 nodes, 10,000 edges
- Automatic fallback to table view for large results

### Caching Strategy

- Metadata cached in frontend store (per session)
- No backend caching (sessions are short-lived)
- Browser caching for static assets

### Scalability

- Stateless backend (can scale horizontally)
- Session data in memory (consider Redis for multi-instance)
- Database connection per session (pooling possible)

---

## Future Enhancements

### Planned Features

1. **Advanced Visualizations**
   - Multiple graph layouts
   - Custom node/edge styling
   - Edge width mapping
   - Neighborhood expansion

2. **Performance**
   - Result streaming for large datasets
   - Canvas rendering for large graphs
   - Query result pagination

3. **Collaboration**
   - Shared saved queries
   - Query templates library
   - Export/import workspaces

4. **Analytics**
   - Graph algorithms (PageRank, centrality)
   - Path finding (shortest path, all paths)
   - Community detection

---

**Last Updated:** February 2026

