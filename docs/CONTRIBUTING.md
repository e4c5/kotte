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
   ```

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
pip install -r requirements-dev.txt

# Production dependencies only
pip install -r requirements.txt
```

#### 3. Configure Environment

Create a `.env` file in the `backend/` directory:

```env
# Development settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

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
MASTER_ENCRYPTION_KEY=your-master-key-here  # or auto-generated in dev
```

**⚠️ IMPORTANT SECURITY NOTES**:
- **NEVER commit `.env` files to version control** (already in `.gitignore`)
- **NEVER commit `.master_encryption_key` files** (already in `.gitignore`)
- Set restrictive file permissions: `chmod 600 .env` and `chmod 600 .master_encryption_key`
- In production, use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Generate strong secrets: `openssl rand -urlsafe 32` for SESSION_SECRET_KEY
- MASTER_ENCRYPTION_KEY must be at least 32 bytes (256 bits)

#### 4. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Access:
- API: <http://localhost:8000>
- Swagger Docs: <http://localhost:8000>/api/docs
- ReDoc: <http://localhost:8000>/api/redoc

### Frontend Setup

The frontend is a React application built with Vite and TypeScript.

#### 1. Install Dependencies

```bash
cd frontend
npm install
```

#### 2. Configure Environment (Optional)

Create a `.env` file in the `frontend/` directory:

```env
VITE_API_BASE_URL=<http://localhost:8000>
```

#### 3. Run Frontend

```bash
npm run dev
```

Access: <http://localhost:5173>

### Database Setup

#### Install PostgreSQL and AGE

**On Ubuntu/Debian:**
```bash
# Install PostgreSQL
sudo apt-get install postgresql-14

# Install AGE (follow official instructions)
# https://age.apache.org/getstarted/installation/
```

**On macOS:**
```bash
# Install PostgreSQL
brew install postgresql@14

# Install AGE
# Follow official instructions
```

**Using Docker:**
```bash
# Run PostgreSQL with AGE
docker run -d \
  --name age-db \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  apache/age
```

#### Initialize Test Database

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create test graph
SELECT create_graph('test_graph');

-- Add sample data
SELECT * FROM cypher('test_graph', $$
  CREATE (a:Person {name: 'Alice', age: 30})
  CREATE (b:Person {name: 'Bob', age: 35})
  CREATE (c:Person {name: 'Charlie', age: 28})
  CREATE (a)-[:KNOWS {since: 2020}]->(b)
  CREATE (b)-[:KNOWS {since: 2021}]->(c)
  CREATE (c)-[:KNOWS {since: 2019}]->(a)
  RETURN a, b, c
$$) AS (a agtype, b agtype, c agtype);
```

---

## Project Structure

```
kotte/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   └── v1/
│   │   │       ├── session.py       # Session management
│   │   │       ├── graph.py         # Graph operations
│   │   │       ├── query.py         # Query execution
│   │   │       ├── import_csv.py    # CSV import
│   │   │       └── health.py        # Health checks
│   │   ├── core/              # Core functionality
│   │   │   ├── auth.py              # Authentication
│   │   │   ├── config.py            # Configuration
│   │   │   ├── database.py          # Database connection
│   │   │   ├── errors.py            # Error handling
│   │   │   ├── middleware.py        # Middleware (CORS, rate limiting)
│   │   │   └── security.py          # Security utilities
│   │   ├── models/            # Pydantic models
│   │   │   ├── session.py           # Session models
│   │   │   ├── graph.py             # Graph models
│   │   │   ├── query.py             # Query models
│   │   │   └── errors.py            # Error models
│   │   ├── services/          # Business logic
│   │   │   ├── agtype.py            # AGE type parsing
│   │   │   ├── metadata.py          # Metadata discovery
│   │   │   └── connection_storage.py # Credential storage
│   │   └── main.py            # Application entry point
│   ├── tests/                 # Test suite
│   │   ├── unit/              # Unit tests
│   │   └── integration/       # Integration tests
│   ├── requirements.txt       # Production dependencies
│   └── requirements-dev.txt   # Development dependencies
│
├── frontend/                  # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── GraphView.tsx        # D3.js graph visualization
│   │   │   ├── TableView.tsx        # Table results view
│   │   │   ├── QueryEditor.tsx      # Cypher query editor
│   │   │   ├── GraphControls.tsx    # Graph layout controls
│   │   │   └── MetadataSidebar.tsx  # Metadata explorer
│   │   ├── pages/             # Page components
│   │   │   ├── ConnectionPage.tsx   # Database connection
│   │   │   └── WorkspacePage.tsx    # Main workspace
│   │   ├── services/          # API client
│   │   │   ├── api.ts               # Base API client
│   │   │   ├── session.ts           # Session API
│   │   │   ├── graph.ts             # Graph API
│   │   │   └── query.ts             # Query API
│   │   ├── stores/            # State management (Zustand)
│   │   │   ├── sessionStore.ts      # Session state
│   │   │   ├── graphStore.ts        # Graph state
│   │   │   └── queryStore.ts        # Query state
│   │   ├── types/             # TypeScript types
│   │   └── App.tsx            # Root component
│   ├── tests/                 # Frontend tests
│   └── package.json           # Dependencies
│
├── docs/                      # Documentation
│   ├── USER_GUIDE.md          # User guide
│   ├── ARCHITECTURE.md        # Architecture documentation
│   ├── CONTRIBUTING.md        # This file
│   └── QUICKSTART.md          # Quick start guide
│
├── Makefile                   # Development commands
└── README.md                  # Project overview
```

---

## Architecture Overview

For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).

### Key Concepts

#### Backend Architecture

1. **FastAPI Application**: Asynchronous Python web framework
2. **Session-Based Authentication**: Secure session cookies with encryption
3. **PostgreSQL + AGE**: Graph database powered by Apache AGE extension
4. **Pydantic Models**: Type-safe request/response validation
5. **Structured Errors**: Consistent error responses with error codes

#### Frontend Architecture

1. **React + TypeScript**: Type-safe component library
2. **Vite**: Fast build tool and dev server
3. **Zustand**: Lightweight state management
4. **D3.js**: Graph visualization library
5. **React Router**: Client-side routing

#### Security Model

1. **Session Management**: HttpOnly cookies, session timeout
2. **Credential Encryption**: AES-256-GCM encryption for stored credentials
3. **CSRF Protection**: CSRF tokens on state-changing requests
4. **Rate Limiting**: Per-IP and per-user rate limits
5. **Input Validation**: Strict validation on all inputs

---

## Development Workflow

### Making Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/feature-name
   ```

2. **Make Changes**
   - Write code following style guide
   - Add tests for new functionality
   - Update documentation as needed

3. **Run Tests**
   ```bash
   # Backend tests
   cd backend && pytest

   # Frontend tests
   cd frontend && npm test
   ```

4. **Lint Code**
   ```bash
   # Backend
   make lint-backend

   # Frontend
   make lint-frontend
   ```

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

6. **Push and Create PR**
   ```bash
   git push origin feature/feature-name
   # Create pull request on GitHub
   ```

### Commit Message Guidelines

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(query): add query cancellation support
fix(auth): resolve session timeout issue
docs(readme): update installation instructions
test(graph): add integration tests for metadata
```

---

## Coding Standards

### Python (Backend)

#### Style Guide

Follow [PEP 8](https://pep8.org/) with these specifics:

- **Line Length**: Maximum 100 characters
- **Indentation**: 4 spaces
- **Imports**: Grouped (stdlib, third-party, local)
- **Type Hints**: Use type hints for all function signatures
- **Docstrings**: Use Google-style docstrings

#### Example

```python
from typing import Optional, List
from pydantic import BaseModel

class GraphMetadata(BaseModel):
    """Graph metadata model.

    Attributes:
        name: Graph name
        node_labels: List of node label names
        edge_types: List of edge type names
    """
    name: str
    node_labels: List[str]
    edge_types: List[str]

async def get_graph_metadata(
    graph_name: str,
    include_counts: bool = False
) -> GraphMetadata:
    """Get metadata for a graph.

    Args:
        graph_name: Name of the graph
        include_counts: Whether to include node/edge counts

    Returns:
        Graph metadata object

    Raises:
        GraphNotFoundError: If graph doesn't exist
    """
    # Implementation
    pass
```

#### Linting Tools

```bash
# Install linting tools
pip install black isort mypy pylint

# Format code
black .

# Sort imports
isort .

# Type checking
mypy .

# Linting
pylint app/
```

### TypeScript (Frontend)

#### Style Guide

- **Line Length**: Maximum 100 characters
- **Indentation**: 2 spaces
- **Quotes**: Single quotes for strings
- **Semicolons**: Use semicolons
- **Type Safety**: Avoid `any`, use explicit types

#### Example

```typescript
interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const fetchGraphData = async (
  graphName: string,
  query: string
): Promise<GraphData> => {
  const response = await api.post('/queries/execute', {
    graph: graphName,
    query: query,
  });

  return response.data;
};
```

#### Linting Tools

```bash
# Install ESLint and Prettier
npm install --save-dev eslint prettier eslint-config-prettier eslint-plugin-react

# Lint code
npm run lint

# Format code
npm run format
```

**Recommended ESLint Configuration** (`.eslintrc.js`):
```javascript
module.exports = {
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier'
  ],
  rules: {
    'quotes': ['error', 'single'],
    'semi': ['error', 'always'],
    'max-len': ['error', { code: 100 }]
  }
};
```

**Prettier Configuration** (`.prettierrc`):
```json
{
  "singleQuote": true,
  "semi": true,
  "printWidth": 100,
  "tabWidth": 2
}
```

---

## Testing Guidelines

### Backend Testing

#### Unit Tests

Test individual functions and methods in isolation.

**Location**: `backend/tests/unit/`

**Example**:
```python
import pytest
from app.services.agtype import parse_agtype

def test_parse_agtype_vertex():
    """Test parsing AGE vertex type."""
    input_data = '{"id": 1, "label": "Person", "properties": {"name": "Alice"}}'
    result = parse_agtype(input_data)

    assert result['id'] == '1'
    assert result['label'] == 'Person'
    assert result['properties']['name'] == 'Alice'

def test_parse_agtype_invalid():
    """Test parsing invalid agtype data."""
    with pytest.raises(ValueError):
        parse_agtype('invalid json')
```

#### Integration Tests

Test API endpoints with a real PostgreSQL + AGE database.

**Location**: `backend/tests/integration/`

**Setup**: Uses Docker Compose to spin up test database

**Example**:
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_connect_and_query(test_db):
    """Test full connection and query flow."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Connect
        response = await client.post('/api/v1/session/connect', json={
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'postgres',
            'password': 'postgres'
        })
        assert response.status_code == 200

        # Execute query
        response = await client.post('/api/v1/queries/execute', json={
            'graph': 'test_graph',
            'query': 'MATCH (n:Person) RETURN n LIMIT 10'
        })
        assert response.status_code == 200
        assert 'results' in response.json()
```

#### Running Tests

```bash
# Run all tests
cd backend && pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_agtype.py

# Run specific test
pytest tests/unit/test_agtype.py::test_parse_agtype_vertex
```

### Frontend Testing

#### Component Tests

Test React components with React Testing Library.

**Location**: `frontend/src/components/__tests__/`

**Example**:
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryEditor } from '../QueryEditor';

describe('QueryEditor', () => {
  it('renders query editor with placeholder', () => {
    render(<QueryEditor onExecute={() => {}} />);
    expect(screen.getByPlaceholderText('Enter Cypher query...')).toBeInTheDocument();
  });

  it('calls onExecute when run button clicked', () => {
    const onExecute = jest.fn();
    render(<QueryEditor onExecute={onExecute} />);

    const textarea = screen.getByPlaceholderText('Enter Cypher query...');
    fireEvent.change(textarea, { target: { value: 'MATCH (n) RETURN n' } });

    const runButton = screen.getByText('Run Query');
    fireEvent.click(runButton);

    expect(onExecute).toHaveBeenCalledWith('MATCH (n) RETURN n');
  });
});
```

#### Running Tests

```bash
# Run all tests
cd frontend && npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watch
```

---

## Security Considerations

### Credential Storage

Kotte uses encrypted credential storage for saved connections.

#### Encryption Details

- **Algorithm**: AES-256-GCM (Galois/Counter Mode)
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **Salt**: Unique salt per credential
- **Authenticated Encryption**: GCM provides both encryption and authentication

#### Key Management

**Development**:
- If `MASTER_ENCRYPTION_KEY` is not set, a key is auto-generated
- Key is persisted to `.master_encryption_key` file
- File is created next to connections file with restrictive permissions (600)

**Production**:
- `MASTER_ENCRYPTION_KEY` **must** be set in environment
- Use a secret manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate key periodically
- Never commit key to version control

#### Implementation

**Storage Service** (`app/services/connection_storage.py`):
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag
import os
import base64

class EncryptedConnectionStorage:
    """Secure credential storage with AES-256-GCM encryption."""

    def __init__(self, master_key: str):
        """Initialize with master encryption key.

        Args:
            master_key: Master encryption key (must be at least 32 bytes)

        Raises:
            ValueError: If master key is too short
        """
        if len(master_key) < 32:
            raise ValueError("Master encryption key must be at least 32 bytes")
        self.master_key = master_key.encode()

    def encrypt_credential(self, credential: str, salt: bytes) -> str:
        """Encrypt a credential using AES-256-GCM.

        Args:
            credential: Plaintext credential
            salt: Unique salt for key derivation (16 bytes recommended)

        Returns:
            Base64-encoded nonce + ciphertext (includes authentication tag)

        Note:
            The returned value contains: nonce (12 bytes) + ciphertext + tag (16 bytes)
            AESGCM.encrypt() returns ciphertext with the authentication tag appended.
        """
        # Derive key from master key + salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=100000
        )
        key = kdf.derive(self.master_key)

        # Encrypt with AES-256-GCM
        # Optional: Add authenticated associated data (AAD) for additional context
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = aesgcm.encrypt(nonce, credential.encode(), None)

        # Return nonce + ciphertext (which includes tag) as base64
        # Format: [nonce: 12 bytes][ciphertext + tag: variable]
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt_credential(self, encrypted_data: str, salt: bytes) -> str:
        """Decrypt a credential using AES-256-GCM.

        Args:
            encrypted_data: Base64-encoded nonce + ciphertext + tag
            salt: Same salt used for encryption

        Returns:
            Decrypted plaintext credential

        Raises:
            InvalidTag: If authentication tag verification fails
            ValueError: If encrypted data is malformed
        """
        try:
            # Decode base64
            data = base64.b64decode(encrypted_data)

            # Split nonce and ciphertext
            if len(data) < 13:  # Minimum: 12-byte nonce + 1 byte ciphertext
                raise ValueError("Encrypted data is too short")

            nonce = data[:12]
            ciphertext = data[12:]  # Includes authentication tag

            # Derive key from master key + salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000
            )
            key = kdf.derive(self.master_key)

            # Decrypt with AES-256-GCM
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            return plaintext.decode()

        except InvalidTag:
            # Authentication failed - data was tampered with
            raise ValueError("Credential decryption failed: authentication tag mismatch")
        except Exception as e:
            raise ValueError(f"Credential decryption failed: {e}")
```

**Important Security Notes**:
- The master encryption key must be at least 32 bytes (256 bits)
- Never commit `.master_encryption_key` to version control (already in `.gitignore`)
- Set file permissions to 600: `chmod 600 .master_encryption_key`
- In production, retrieve the key from a secret manager, not a file
- GCM provides authenticated encryption - tampering is detected automatically
- Consider adding AAD (authenticated associated data) for additional context binding

### SQL Injection Prevention

#### Parameterized Queries

**Always use parameterized queries** for user input.

**Important**: This project uses **psycopg 3** (async driver). The async signature is:
```python
await conn.execute(query, params)  # NOT execute(query, *params)
```

**Correct examples**:

```python
# ✅ CORRECT - psycopg3 async with dict parameters
query = """
    SELECT * FROM cypher(%(graph)s, %(cypher)s) AS (result agtype)
"""
params = {"graph": graph_name, "cypher": cypher_query}
await conn.execute(query, params)

# ✅ CORRECT - psycopg3 async with positional parameters
query = """
    SELECT * FROM cypher($1, $2) AS (result agtype)
"""
params = (graph_name, cypher_query)
await conn.execute(query, params)

# ❌ WRONG - SQL injection risk
query = f"SELECT * FROM cypher('{graph_name}', '{cypher_query}')"
await conn.execute(query)

# ❌ WRONG - Incorrect psycopg3 async signature
await conn.execute(query, *params)  # Don't unpack params
```

#### Identifier Validation

Graph names, label names, and other identifiers must be validated:

```python
import re

def validate_identifier(name: str) -> bool:
    """Validate PostgreSQL/AGE identifier.

    Args:
        name: Identifier to validate

    Returns:
        True if valid, False otherwise
    """
    # Must start with letter or underscore
    # Can contain letters, digits, underscores
    # Max 63 characters (PostgreSQL limit)
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_]{0,62}$'
    return bool(re.match(pattern, name))
```

### Input Validation

All API inputs must be validated with Pydantic models:

```python
from pydantic import BaseModel, Field, validator

class QueryRequest(BaseModel):
    """Query execution request."""

    graph: str = Field(..., min_length=1, max_length=63)
    query: str = Field(..., min_length=1, max_length=10000)
    parameters: dict = Field(default_factory=dict)

    @validator('graph')
    def validate_graph_name(cls, v):
        """Validate graph name format."""
        if not validate_identifier(v):
            raise ValueError('Invalid graph name format')
        return v

    @validator('query')
    def validate_query_length(cls, v):
        """Validate query is not too long."""
        if len(v) > 10000:
            raise ValueError('Query too long (max 10000 characters)')
        return v
```

### Rate Limiting

Rate limiting prevents abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/queries/execute")
@limiter.limit("60/minute")
async def execute_query(request: Request):
    """Execute query with rate limiting."""
    # Implementation
    pass
```

### Session Storage (Production)

**Development**: The default in-memory session storage is fine for development with a single backend instance.

**Production**: For multi-instance deployments, configure a shared session store:

#### Redis Session Store (Recommended)

```python
# backend/app/core/session_store.py
import redis.asyncio as redis
from typing import Optional, Dict, Any
import json

class RedisSessionStore:
    """Redis-backed session storage for production."""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        data = await self.redis.get(f"session:{session_id}")
        return json.loads(data) if data else None

    async def set(self, session_id: str, data: Dict[str, Any], ttl: int = 3600):
        """Set session data with TTL."""
        await self.redis.setex(
            f"session:{session_id}",
            ttl,
            json.dumps(data)
        )

    async def delete(self, session_id: str):
        """Delete session."""
        await self.redis.delete(f"session:{session_id}")
```

**Configuration** (add to `.env`):
```env
# Session storage
SESSION_STORAGE_TYPE=redis  # or "memory" for development
REDIS_URL=redis://localhost:6379/0
```

**Benefits**:
- Shared state across multiple backend instances
- Automatic session expiration via Redis TTL
- Persistence across backend restarts
- High performance and scalability

---

## Pull Request Process

### Before Submitting

1. **Run All Tests**
   ```bash
   make test-backend
   make test-frontend
   ```

2. **Lint Code**
   ```bash
   make lint-backend
   make lint-frontend
   ```

3. **Update Documentation**
   - Update relevant docs if behavior changes
   - Add docstrings for new functions/classes
   - Update API documentation if endpoints change

4. **Check Security**
   - No hardcoded secrets
   - Input validation on new endpoints
   - Parameterized queries for database operations

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No security issues introduced
- [ ] CI checks pass (linting, tests, docs)
```

### Review Process

1. **Automated Checks**: CI runs tests, linting, and documentation checks (see `.github/workflows/`)
2. **Code Review**: Maintainer reviews code
3. **Feedback**: Address any requested changes
4. **Approval**: Maintainer approves PR
5. **Merge**: PR is merged to main branch

### CI Workflows

The project uses GitHub Actions for automated checks:

- **Backend Tests** (`.github/workflows/backend.yml`): Runs pytest, type checking, linting
- **Frontend Tests** (`.github/workflows/frontend.yml`): Runs npm test, ESLint, type checking
- **Documentation Checks** (`.github/workflows/docs.yml`): Markdown linting, link checking, spell checking

To run checks locally before pushing:

```bash
# Backend
make lint-backend
make test-backend

# Frontend
make lint-frontend
make test-frontend

# Documentation
markdownlint docs/*.md README.md
markdown-link-check docs/*.md README.md
```

---

## Documentation Maintenance

### Keeping Documentation In Sync

When making changes to the codebase, update the relevant documentation:

#### API Changes
- **New Endpoints**: Add to `ARCHITECTURE.md` API Reference section with request/response examples
- **Changed Endpoints**: Update examples in `ARCHITECTURE.md` and `USER_GUIDE.md`
- **Removed Endpoints**: Remove from all documentation

#### Features
- **New Features**:
  - Add to `README.md` Key Features section
  - Document usage in `USER_GUIDE.md`
  - Add technical details to `ARCHITECTURE.md`
- **Configuration Changes**: Update `.env` examples in `CONTRIBUTING.md`
- **Security Changes**: Document in `CONTRIBUTING.md` Security Considerations

#### Architecture Changes
- **New Components**: Add to `ARCHITECTURE.md` directory structure and component descriptions
- **New Dependencies**: Update technology stack in `CONTRIBUTING.md`
- **Deployment Changes**: Update `ARCHITECTURE.md` Deployment Architecture section

### Documentation Structure

```
docs/
├── USER_GUIDE.md         # End-user documentation
│   └── Update when: Adding user-facing features, UI changes, troubleshooting
├── QUICKSTART.md         # Quick setup guide
│   └── Update when: Changing installation steps, prerequisites
├── ARCHITECTURE.md       # Technical architecture
│   └── Update when: API changes, architecture changes, deployment patterns
└── CONTRIBUTING.md       # Developer guide
    └── Update when: Development workflow changes, coding standards, security practices
```

### Documentation Review Checklist

Before submitting a PR:

- [ ] All code examples tested and working
- [ ] Links checked (internal and external)
- [ ] Markdown formatting consistent
- [ ] Screenshots updated if UI changed
- [ ] Version numbers current
- [ ] No TODO or placeholder content

### Running Documentation Checks

```bash
# Check for broken links
npm install -g markdown-link-check
find docs -name "*.md" -exec markdown-link-check {} \;

# Lint markdown files
npm install -g markdownlint-cli
markdownlint docs/*.md README.md

# Spell check (optional)
npm install -g cspell
cspell "docs/**/*.md" README.md
```

---

## Common Tasks

### Adding a New API Endpoint

1. **Define Model** (`app/models/`):
   ```python
   class NewFeatureRequest(BaseModel):
       param1: str
       param2: int
   ```

2. **Create Endpoint** (`app/api/v1/`):
   ```python
   @router.post("/new-feature")
   async def new_feature(
       request: NewFeatureRequest,
       session: dict = Depends(get_session)
   ) -> NewFeatureResponse:
       # Implementation
       pass
   ```

3. **Add Tests**:
   - Unit test for business logic
   - Integration test for endpoint

4. **Update Documentation**:
   - API docs auto-generated from code
   - Update user guide if user-facing

### Adding a New Frontend Component

1. **Create Component** (`src/components/`):
   ```typescript
   interface NewComponentProps {
     data: GraphData;
     onAction: (id: string) => void;
   }

   export const NewComponent: React.FC<NewComponentProps> = ({
     data,
     onAction
   }) => {
     return (
       <div>
         {/* Implementation */}
       </div>
     );
   };
   ```

2. **Add Tests**:
   ```typescript
   describe('NewComponent', () => {
     it('renders correctly', () => {
       // Test implementation
     });
   });
   ```

3. **Use Component**:
   ```typescript
   import { NewComponent } from './components/NewComponent';

   // In parent component
   <NewComponent data={graphData} onAction={handleAction} />
   ```

### Adding Database Migrations

Kotte doesn't use traditional migrations (AGE manages schema). For setup scripts:

1. **Create Script** (`scripts/setup_graph.sql`):
   ```sql
   -- Create graph
   SELECT create_graph('new_graph');

   -- Add sample data
   SELECT * FROM cypher('new_graph', $$
     CREATE (n:NewLabel {property: 'value'})
     RETURN n
   $$) AS (n agtype);
   ```

2. **Document** in QUICKSTART.md or relevant docs

---

## Resources

### Internal Documentation

- [Architecture Documentation](ARCHITECTURE.md)
- [User Guide](USER_GUIDE.md)
- [Quick Start Guide](QUICKSTART.md)

### External Resources

- [Apache AGE Documentation](https://age.apache.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/e4c5/kotte/issues)
- **Discussions**: [GitHub Discussions](https://github.com/e4c5/kotte/discussions)

---

Thank you for contributing to Kotte! Your contributions help make graph database visualization better for everyone.

**Last Updated:** February 2026*
