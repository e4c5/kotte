# Gap Filling Checklist

Quick reference checklist for tracking gap resolution progress.

## Critical (Release Blockers)

- [ ] **Authentication System**
  - [ ] Add `POST /api/v1/auth/login` endpoint
  - [ ] Add `POST /api/v1/auth/logout` endpoint
  - [ ] Require authentication before connection
  - [ ] Add audit logging for auth events
  - [ ] Update frontend with login page
  - [ ] **Encrypted Credential Storage (Production)**
    - [ ] Implement credential encryption service (AES-256-GCM with PBKDF2)
    - [ ] Create connection storage service (encrypted JSON file, separate from Apache AGE DB)
    - [ ] Set up key management (environment/secret manager)
    - [ ] Configure storage path and file permissions (600)
    - [ ] Add save/load/update/delete connection endpoints
    - [ ] Encrypt credentials in session storage
    - [ ] Add audit logging for credential operations
    - [ ] Update frontend with saved connections UI

- [ ] **Security Hardening**
  - [ ] Fix SQL injection in query execution (graph name parameterization)
  - [ ] Fix SQL injection in CSV import (graph/label name parameterization)
  - [ ] Add CSRF protection
  - [ ] Add rate limiting middleware
  - [ ] Add dependency scanning to CI
  - [ ] Add input validation for graph/label names

- [ ] **Query Cancellation**
  - [ ] Track active queries with backend PIDs
  - [ ] Implement `pg_cancel_backend()` cancellation
  - [ ] Add timeout enforcement
  - [ ] Add cancel button to frontend

## High Priority (Production Required)

- [ ] **Testing Infrastructure**
  - [ ] Backend unit tests (>80% coverage)
  - [ ] Backend integration tests with AGE
  - [ ] Frontend component tests
  - [ ] E2E smoke tests
  - [ ] CI version matrix (PostgreSQL 14/15/16)

- [ ] **Oversized Result Handling**
  - [ ] Add visualization caps (5k nodes, 10k edges)
  - [ ] Auto-switch to table view when cap exceeded
  - [ ] Add guidance messages for query refinement
  - [ ] Add configurable limits

## Medium Priority

- [ ] **Neighborhood Expansion**
  - [ ] Add `POST /graphs/{graph}/nodes/{id}/expand` endpoint
  - [ ] Add right-click context menu
  - [ ] Add expand action to menu
  - [ ] Merge expanded nodes into graph

- [ ] **Edge Width Mapping**
  - [ ] Add property statistics to metadata
  - [ ] Add width mapping control to GraphControls
  - [ ] Implement d3 scale mapping
  - [ ] Update GraphView to use mapped widths

- [ ] **Node Deletion**
  - [ ] Add `DELETE /graphs/{graph}/nodes/{id}` endpoint
  - [ ] Add delete action to context menu
  - [ ] Add confirmation dialog
  - [ ] Refresh graph after deletion

- [ ] **Result Streaming**
  - [ ] Implement streaming response endpoint
  - [ ] Add pagination to table view
  - [ ] Add virtual scrolling
  - [ ] Add "Load more" functionality

- [ ] **PNG Export**
  - [ ] Add export button to graph view
  - [ ] Implement SVG to PNG conversion
  - [ ] Add download functionality

## Low Priority

- [ ] **Settings Persistence**
  - [ ] Add settings store with localStorage
  - [ ] Persist theme preference
  - [ ] Persist layout defaults
  - [ ] Persist data limits

- [ ] **Multi-Result Panels**
  - [ ] Add tabbed interface
  - [ ] Add close/refresh/pin actions
  - [ ] Support multiple query results

- [ ] **Accessibility**
  - [ ] Add ARIA labels to all interactive elements
  - [ ] Add keyboard navigation
  - [ ] Ensure WCAG AA contrast compliance
  - [ ] Add high contrast theme

## Security Checklist (Section 10)

- [ ] Authentication enforced on all protected endpoints
- [ ] Session cookies configured correctly (HttpOnly, SameSite, Secure)
- [ ] Session rotation on auth state changes
- [ ] No hardcoded secrets
- [ ] All secrets from environment
- [ ] Strict schema validation on all API requests
- [ ] CSV import input validation with row-level errors
- [ ] Query parameter validation before DB execution
- [ ] Request size limits configured
- [ ] No unsafe SQL string concatenation
- [ ] Parameterized query execution enforced
- [ ] Safe/read-only mode validated
- [ ] Query timeout and cancellation enabled
- [ ] TLS enabled for deployed endpoints
- [ ] CORS policy restricted
- [ ] Standard error envelope returned
- [ ] Internal stack traces not exposed
- [ ] Sensitive fields excluded from responses
- [ ] Authentication events logged
- [ ] Mutating operations logged
- [ ] Security alerts configured
- [ ] Dependency vulnerability scan passes
- [ ] Lockfiles committed
- [ ] Security-focused integration tests pass
- [ ] Manual penetration checks completed
- [ ] Security sign-off recorded

## Testing Checklist

- [ ] Backend unit tests
  - [ ] agtype parser tests
  - [ ] metadata service tests
  - [ ] error handling tests
  - [ ] validation tests

- [ ] Backend integration tests
  - [ ] Connection/disconnection
  - [ ] Query execution (read/write)
  - [ ] CSV import with rollback
  - [ ] Metadata discovery
  - [ ] Graph switching
  - [ ] Authentication flow

- [ ] Frontend tests
  - [ ] QueryEditor component
  - [ ] GraphView component
  - [ ] TableView component
  - [ ] Error handling

- [ ] E2E tests
  - [ ] Connect → Query → Visualize flow
  - [ ] Error paths
  - [ ] CSV import flow

- [ ] CI Integration
  - [ ] Tests run on PR
  - [ ] Version matrix (PostgreSQL 14/15/16)
  - [ ] Coverage reporting

## Performance Checklist

- [ ] Graph render for 5k nodes + 10k edges < 3s
- [ ] Query result streaming implemented
- [ ] Metadata fetch < 1s
- [ ] Visualization caps enforced
- [ ] UI responsive for oversized results

## Documentation Checklist

- [ ] API documentation updated
- [ ] Architecture documentation updated
- [ ] Security documentation updated
- [ ] Testing documentation updated
- [ ] Deployment guide updated
- [ ] Migration notes for deprecated features

