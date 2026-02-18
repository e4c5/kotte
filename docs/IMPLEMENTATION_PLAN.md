# Implementation Plan: Filling the Gaps

This document provides a detailed plan to address the gaps identified in `GAP_ANALYSIS.md`.

## Phase 1: Critical Security & Authentication (Release Blockers)

### 1.1 Authentication System
**Priority: CRITICAL**  
**Estimated Effort: 4-5 days** (includes encrypted credential storage implementation)

#### Architecture Decision: Database Credentials
**Approach:** Hybrid approach with encrypted credential storage (Option 4 from `SECURE_CREDENTIAL_STORAGE.md`)
- Application authentication and database authentication are separate
- Support both saved connections (encrypted) and one-time connections
- Encrypted credential storage using AES-256-GCM with proper key management
- Credentials encrypted in session storage
- Credentials cleared on logout/disconnect
- Production-grade security with audit logging

#### Tasks:
1. **Create authentication endpoints**
   - `POST /api/v1/auth/login` - Accept username/password or API key
   - `POST /api/v1/auth/logout` - Invalidate session
   - `GET /api/v1/auth/me` - Get current user info
   
2. **Update session management**
   - Require authentication before `/session/connect`
   - Store user identity in session (replace hardcoded `user_id`)
   - Add user model/service for identity management
   - **Implement encrypted credential storage:**
     - Create credential encryption service (AES-256-GCM with PBKDF2)
     - Create connection storage service (encrypted JSON file - separate from Apache AGE database)
     - Encrypt credentials before storing in file
     - Support saving connections per user
     - Support one-time connections (not saved)
     - Encrypt credentials in session storage
     - Clear credentials immediately after connection validation
     - Never log credentials
     - Clear credentials on logout/disconnect
     - Implement credential rotation support
     - Set restrictive file permissions (600)
   
3. **Add audit logging**
   - Log login success/failure with timestamp, IP, user
   - Log logout events
   - Log session expiration/invalidation
   - Log connection attempts (without credentials)
   - Use structured logging with correlation IDs

4. **Update frontend**
   - Add login page before connection page
   - Store auth token/session in secure storage
   - Add logout functionality
   - Connection page requires app auth first

**Files to modify:**
- `backend/app/api/v1/auth.py` (new)
- `backend/app/core/auth.py` (update - add credential encryption)
- `backend/app/core/credentials.py` (new - credential encryption service)
- `backend/app/core/connection_storage.py` (new - JSON file storage service, separate from Apache AGE DB)
- `backend/app/models/auth.py` (new)
- `backend/app/models/connection.py` (new - saved connection models)
- `backend/app/services/user.py` (new)
- `backend/app/api/v1/connections.py` (new - saved connection endpoints)
- `backend/app/api/v1/session.py` (update - require auth, encrypt credentials, support saved connections)
- `backend/app/core/config.py` (update - add credential storage configuration)
- `frontend/src/pages/LoginPage.tsx` (new)
- `frontend/src/services/auth.ts` (new)
- `frontend/src/services/connections.ts` (new - saved connection API)
- `frontend/src/pages/ConnectionPage.tsx` (update - check auth first, support saved connections)
- `frontend/src/components/SavedConnections.tsx` (new - saved connections UI)

**Security Considerations:**
- See `SECURE_CREDENTIAL_STORAGE.md` for detailed security practices
- Master encryption key from environment/secret manager (AWS Secrets Manager, HashiCorp Vault)
- AES-256-GCM encryption for stored credentials
- User-specific key derivation (PBKDF2/Argon2)
- Credentials never logged or returned in API responses
- Session encryption for all credential storage
- Audit logging for all credential operations
- Support for credential rotation
- Rate limiting on connection attempts

---

### 1.2 Security Hardening
**Priority: CRITICAL**  
**Estimated Effort: 3-4 days**

#### Tasks:
1. **Fix SQL injection risks**
   - Parameterize graph name in query execution (line 98 in `query.py`)
   - Parameterize graph/label names in CSV import (lines 66, 126, 133, 166, 179)
   - Use whitelist validation for graph/label names (alphanumeric + underscore only)

2. **Add CSRF protection**
   - Generate CSRF tokens for authenticated sessions
   - Validate CSRF tokens on state-changing requests
   - Use `SameSite=Strict` cookies where applicable

3. **Add rate limiting**
   - Implement rate limiting middleware
   - Limit by IP and/or user
   - Configurable limits per endpoint type
   - Return 429 with retry-after header

4. **Add input validation**
   - Strict Pydantic validation on all endpoints
   - Graph name validation (regex: `^[a-zA-Z_][a-zA-Z0-9_]*$`)
   - Query size limits (max query length)
   - File size limits (already exists, verify enforcement)

5. **Dependency scanning**
   - Add `safety` or `pip-audit` to CI
   - Scan on every PR
   - Block PRs with critical vulnerabilities

**Files to modify:**
- `backend/app/core/middleware.py` (add rate limiting, CSRF)
- `backend/app/api/v1/query.py` (fix SQL injection)
- `backend/app/api/v1/import_csv.py` (fix SQL injection)
- `backend/app/core/validation.py` (new - graph name validation)
- `.github/workflows/security.yml` (new - dependency scanning)

---

### 1.3 Query Cancellation
**Priority: CRITICAL**  
**Estimated Effort: 2 days**

#### Tasks:
1. **Track active queries**
   - Register queries in `_active_queries` dict with:
     - Request ID
     - Database connection
     - PostgreSQL backend PID
     - Start time
     - Session ID

2. **Implement cancellation**
   - Use `pg_cancel_backend(pid)` to cancel PostgreSQL query
   - Query backend PID from `pg_stat_activity`
   - Handle cancellation errors gracefully
   - Clean up query tracking on completion/cancellation

3. **Add timeout enforcement**
   - Use `asyncio.wait_for()` with `settings.query_timeout`
   - Cancel query on timeout
   - Return `QUERY_TIMEOUT` error

4. **Update frontend**
   - Show cancel button during query execution
   - Call cancel endpoint on button click
   - Display cancellation status

**Files to modify:**
- `backend/app/api/v1/query.py` (implement cancellation)
- `backend/app/core/database.py` (add query tracking)
- `frontend/src/components/QueryEditor.tsx` (add cancel button)
- `frontend/src/stores/queryStore.ts` (add cancel state)

---

## Phase 2: High Priority Features (Production Requirements)

### 2.1 CSV Import - NOT REQUIRED
**Status:** CSV import functionality is not required. The existing implementation is sufficient for any future needs. No development needed.

---

### 2.2 Testing Infrastructure
**Priority: HIGH**  
**Estimated Effort: 4-5 days**

#### Tasks:
1. **Backend unit tests**
   - Test agtype parser with various inputs
   - Test metadata service
   - Test error handling
   - Test validation logic

2. **Backend integration tests**
   - Docker Compose setup with PostgreSQL + AGE
   - Test connection/disconnection
   - Test query execution (read/write)
   - Test CSV import with rollback
   - Test metadata discovery
   - Test graph switching

3. **Frontend component tests**
   - Test QueryEditor component
   - Test GraphView rendering
   - Test TableView pagination
   - Test error handling

4. **E2E tests**
   - Playwright or Cypress setup
   - Smoke test: connect → query → visualize
   - Test error paths

5. **CI integration**
   - Run tests on PR
   - Version matrix for PostgreSQL 14/15/16
   - Coverage reporting

**Files to create:**
- `backend/tests/unit/test_agtype.py`
- `backend/tests/unit/test_metadata.py`
- `backend/tests/integration/test_connection.py`
- `backend/tests/integration/test_queries.py`
- `backend/tests/integration/test_import.py`
- `backend/docker-compose.test.yml`
- `frontend/src/components/__tests__/QueryEditor.test.tsx`
- `frontend/e2e/smoke.spec.ts`
- `.github/workflows/test.yml`

---

### 2.3 Oversized Result Handling
**Priority: HIGH**  
**Estimated Effort: 1-2 days**

#### Tasks:
1. **Add visualization caps**
   - Config: `max_nodes_for_graph`, `max_edges_for_graph` (default: 5000, 10000)
   - Check caps before graph rendering
   - Return warning in response if cap exceeded

2. **Update frontend**
   - Check node/edge counts before rendering graph
   - Show message: "Result too large for graph view. Use table view or refine query."
   - Auto-switch to table view if cap exceeded
   - Show counts in UI

3. **Add guidance**
   - Suggest query refinements (add LIMIT, add WHERE filters)
   - Link to query builder or examples

**Files to modify:**
- `backend/app/core/config.py` (add cap settings)
- `backend/app/api/v1/query.py` (check caps, add warning)
- `backend/app/models/query.py` (add warning field)
- `frontend/src/pages/WorkspacePage.tsx` (check caps, show message)

---

## Phase 3: Medium Priority Features

### 3.1 Neighborhood Expansion
**Priority: MEDIUM**  
**Estimated Effort: 2 days**

#### Tasks:
1. **Backend endpoint**
   - `POST /api/v1/graphs/{graph}/nodes/{id}/expand`
   - Accept `depth` (default: 1) and `limit` (default: 100)
   - Execute Cypher: `MATCH (n)-[*1..depth]-(m) WHERE id(n) = $id RETURN ...`
   - Return subgraph (nodes + edges)

2. **Frontend UI**
   - Right-click context menu on nodes
   - "Expand Neighborhood" option
   - Merge new nodes/edges into existing graph
   - Visual indicator for newly expanded nodes

**Files to modify:**
- `backend/app/api/v1/graph.py` (add expand endpoint)
- `backend/app/models/graph.py` (add expand request/response)
- `frontend/src/components/GraphView.tsx` (add context menu)
- `frontend/src/services/graph.ts` (add expand API call)

---

### 3.2 Edge Width Mapping
**Priority: MEDIUM**  
**Estimated Effort: 1 day**

#### Tasks:
1. **Backend support**
   - Return numeric property ranges in metadata
   - Include edge property statistics

2. **Frontend implementation**
   - Add edge width mapping control in GraphControls
   - Map numeric property to edge stroke-width
   - Use d3 scale for mapping (linear or log)
   - Update GraphView to use mapped widths

**Files to modify:**
- `backend/app/models/graph.py` (add property stats)
- `frontend/src/components/GraphControls.tsx` (add width mapping)
- `frontend/src/stores/graphStore.ts` (add width mapping state)
- `frontend/src/components/GraphView.tsx` (apply width mapping)

---

### 3.3 Node Deletion (Optional)
**Priority: MEDIUM**  
**Estimated Effort: 1-2 days**

#### Tasks:
1. **Backend endpoint**
   - `DELETE /api/v1/graphs/{graph}/nodes/{id}`
   - Accept `detach` parameter (default: false)
   - Execute: `MATCH (n) WHERE id(n) = $id [DETACH] DELETE n`
   - Return deletion summary

2. **Frontend UI**
   - Add "Delete Node" to context menu
   - Confirmation dialog
   - Refresh graph after deletion

**Files to modify:**
- `backend/app/api/v1/graph.py` (add delete endpoint)
- `frontend/src/components/GraphView.tsx` (add delete action)
- `frontend/src/services/graph.ts` (add delete API call)

---

### 3.4 Result Streaming
**Priority: MEDIUM**  
**Estimated Effort: 2-3 days**

#### Tasks:
1. **Backend streaming**
   - Use FastAPI StreamingResponse
   - Stream results in chunks (e.g., 1000 rows)
   - Support pagination with cursor/offset

2. **Frontend pagination**
   - Load results in pages
   - Virtual scrolling for table view
   - "Load more" button or infinite scroll

**Files to modify:**
- `backend/app/api/v1/query.py` (add streaming endpoint)
- `frontend/src/components/TableView.tsx` (add pagination)
- `frontend/src/stores/queryStore.ts` (add pagination state)

---

### 3.5 PNG Export
**Priority: MEDIUM**  
**Estimated Effort: 1 day**

#### Tasks:
1. **Backend endpoint**
   - `GET /api/v1/queries/{requestId}/export/png`
   - Generate PNG from graph data (server-side) OR
   - Return data for client-side export

2. **Frontend implementation**
   - Use html2canvas or similar
   - Export SVG to PNG
   - Download PNG file

**Files to modify:**
- `frontend/src/components/GraphView.tsx` (add export function)
- `frontend/src/pages/WorkspacePage.tsx` (add export button)

---

## Phase 4: Observability & Production Readiness

### 4.1 Observability and Monitoring
**Priority: MEDIUM** (Required for Production)  
**Estimated Effort: 2-3 days**

#### Tasks:
1. **Metrics Collection**
   - Add Prometheus metrics endpoint (`/metrics`)
   - Track query latency (histogram)
   - Track error rates (counter)
   - Track active sessions (gauge)
   - Track connection attempts (counter)

2. **Structured Logging**
   - Request/session correlation IDs (already implemented)
   - Query execution logging (without credentials)
   - Connection event logging
   - Error context logging

3. **Performance Monitoring**
   - Query duration tracking
   - Graph render time tracking
   - Database connection pool metrics
   - Memory usage monitoring

4. **Health Checks**
   - `/health` endpoint
   - `/ready` endpoint (database connectivity check)
   - Dependency health (database, session store)

**Files to modify:**
- `backend/app/core/metrics.py` (new)
- `backend/app/api/v1/health.py` (new)
- `backend/app/core/middleware.py` (add metrics collection)
- `backend/prometheus.yml` (new - if using Prometheus)

---

## Phase 5: Low Priority / Polish

### 5.1 Settings Persistence
**Priority: LOW**  
**Estimated Effort: 1 day**

#### Tasks:
1. **Frontend localStorage**
   - Save theme preference
   - Save layout defaults
   - Save data limits
   - Load on app start

**Files to modify:**
- `frontend/src/stores/settingsStore.ts` (new)
- `frontend/src/components/SettingsModal.tsx` (new)

---

### 5.2 Multi-Result Panels
**Priority: LOW**  
**Estimated Effort: 2-3 days**

#### Tasks:
1. **Frontend tabs/panels**
   - Tabbed interface for multiple results
   - Each tab has query, graph/table view
   - Close, refresh, pin tabs

**Files to modify:**
- `frontend/src/pages/WorkspacePage.tsx` (refactor to tabs)
- `frontend/src/components/ResultTab.tsx` (new)

---

### 5.3 Accessibility
**Priority: LOW**  
**Estimated Effort: 2 days**

#### Tasks:
1. **ARIA labels**
   - Add labels to all interactive elements
   - Add roles and descriptions

2. **Keyboard navigation**
   - Tab order
   - Keyboard shortcuts for all actions
   - Focus management

3. **Contrast compliance**
   - WCAG AA contrast ratios
   - High contrast theme option

**Files to modify:**
- All frontend components (add ARIA attributes)

---

## Implementation Timeline

### Week 1: Critical Security
- Day 1-2: Authentication system
- Day 3-4: Security hardening (SQL injection fixes, CSRF, rate limiting)
- Day 5: Query cancellation

### Week 2: High Priority Production Features
- Day 1-3: Testing infrastructure setup
- Day 4-5: Oversized result handling

**Note:** CSV import removed from scope - not required.

### Week 3: Medium Priority
- Day 1-2: Neighborhood expansion
- Day 3: Edge width mapping
- Day 4-5: Node deletion + Result streaming

### Week 4: Observability & Production Readiness
- Day 1-2: Observability and monitoring (metrics, logging, health checks)
- Day 3: Complete test coverage
- Day 4-5: Performance optimization and benchmarking

### Week 5: Polish & Final Testing
- Day 1: PNG export
- Day 2: Settings persistence
- Day 3-4: Accessibility improvements
- Day 5: Final security audit and documentation

---

## Risk Mitigation

1. **Authentication complexity** - Start with simple username/password, add OAuth later
2. **Testing setup** - Use Docker Compose for consistent test environment
3. **Performance** - Profile and optimize iteratively, set up benchmarks

---

## Success Criteria

- All CRITICAL gaps resolved
- All HIGH priority gaps resolved
- All MEDIUM priority gaps resolved (production-ready features)
- Test coverage > 80%
- Security checklist (Section 10) passes
- All production acceptance criteria (Section 13) met
- Performance benchmarks met (5k nodes + 10k edges < 3s render)
- Observability and monitoring in place
- Production deployment documentation complete

