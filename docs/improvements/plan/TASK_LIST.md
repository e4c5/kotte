# Task List - Apache AGE Visualizer Implementation

This document provides a comprehensive, actionable task list for implementing all identified improvements to the Kotte Apache AGE visualizer. Each task references detailed analysis documents that explain the issue, provide code examples, and offer implementation guidance.

## 📚 Related Analysis Documents

Before implementing tasks, review these analysis documents for context and detailed explanations:

- **[Executive Summary](../analysis/00_EXECUTIVE_SUMMARY.md)** - Overall quality assessment and roadmap
- **[At-a-Glance Analysis](../analysis/ANALYSIS_AT_A_GLANCE.md)** - Quick visual summary and health scores
- **[Security Gaps](../analysis/01_SECURITY_GAPS.md)** - Critical SQL injection risks and fixes
- **[Performance Optimization](../analysis/02_PERFORMANCE_OPTIMIZATION.md)** - Database indexing and query optimization
- **[Transaction Handling](../analysis/03_TRANSACTION_HANDLING.md)** - ACID compliance requirements
- **[Error Handling](../analysis/04_ERROR_HANDLING_IMPROVEMENTS.md)** - Graph-specific exception types
- **[AGE Features](../analysis/05_AGE_FEATURE_UTILIZATION.md)** - Advanced AGE capabilities
- **[Visualization Optimization](../analysis/06_VISUALIZATION_QUERY_OPTIMIZATION.md)** - Query-time limits
- **[Path Handling](../analysis/07_PATH_HANDLING_IMPROVEMENTS.md)** - Path semantics preservation
- **[Testing Recommendations](../analysis/08_TESTING_RECOMMENDATIONS.md)** - Comprehensive test strategy

---

## Phase 1: Critical Security & Data Integrity (Week 1-2)

**📖 Analysis Reference:** See [Security Gaps](../analysis/01_SECURITY_GAPS.md) and [Transaction Handling](../analysis/03_TRANSACTION_HANDLING.md)

### Security Fixes (HIGH Priority - 10 hours)

**Detailed guidance:** [01_SECURITY_GAPS.md - Gap #1, #2, #3](../analysis/01_SECURITY_GAPS.md)

- [x] Fix unvalidated graph_name in graph.py:209
  - **File:** `backend/app/api/v1/graph.py:209`
  - **Issue:** Graph name used without validation before database query
  - **Fix:** Add `validate_graph_name()` call before line 221
  - **Reference:** Security Gaps, Gap #1
  
- [x] Implement escape_identifier() utility
  - **File:** `backend/app/core/validation.py`
  - **Issue:** Need PostgreSQL identifier escaping for defense-in-depth
  - **Fix:** Add `escape_identifier()` function
  - **Reference:** Security Gaps, Gap #2 - Step 1
  
- [x] Apply escaping to metadata.py (3 locations)
  - **File:** `backend/app/services/metadata.py` lines 36-73, 82-120, 145-198
  - **Issue:** F-string table names without escaping
  - **Fix:** Use `escape_identifier()` for all table names
  - **Reference:** Security Gaps, Gap #2 - Step 2
  
- [x] Apply escaping to graph.py:269
  - **File:** `backend/app/api/v1/graph.py:269-285`
  - **Issue:** F-string query construction
  - **Fix:** Apply `escape_identifier()` to validated names
  - **Reference:** Security Gaps, Gap #2 - Step 3
  
- [x] Apply escaping to import_csv.py (2 locations)
  - **File:** `backend/app/api/v1/import_csv.py` lines 69-75, 134-148
  - **Issue:** String interpolation in AGE function calls
  - **Fix:** Use `escape_identifier()` with defensive comments
  - **Reference:** Security Gaps, Gap #3
  
- [x] Add unit tests for escape_identifier()
  - **File:** `backend/tests/test_validation.py`
  - **Tests:** Basic identifiers, quotes, malicious input
  - **Reference:** Security Gaps, Testing section
  
- [x] Security review of all f-string queries
  - **Action:** Audit all database queries for string interpolation
  - **Tool:** Use grep/automated scanning
  - **Reference:** Security Gaps, Additional Recommendations

### Transaction Protection (HIGH Priority - 23 hours)

**Detailed guidance:** [03_TRANSACTION_HANDLING.md](../analysis/03_TRANSACTION_HANDLING.md)

- [x] Wrap node deletion in transaction
  - **File:** `backend/app/api/v1/graph_delete_node.py:60-152`
  - **Issue:** Node deletion not atomic
  - **Fix:** Wrap count + delete in `async with db_conn.transaction()`
  - **Reference:** Transaction Handling, Gap #1
  
- [x] Add deletion verification
  - **File:** `backend/app/api/v1/graph_delete_node.py`
  - **Issue:** No verification that deletion succeeded
  - **Fix:** Check deleted_count > 0, raise exception if 0
  - **Reference:** Transaction Handling, Gap #1 - Fixed Implementation
  
- [x] CSV pre-validation implementation
  - **File:** `backend/app/api/v1/import.py`
  - **Issue:** Validation happens during insert
  - **Fix:** Add Phase 1 validation before any DB operations
  - **Reference:** Transaction Handling, Gap #2 - Phase 1
  
- [x] Move graph/label creation into transaction
  - **File:** `backend/app/api/v1/import.py`
  - **Issue:** Graph creation outside transaction
  - **Fix:** Move into transaction block
  - **Reference:** Transaction Handling, Gap #2 - Phase 2
  
- [x] Implement batch insertion (1000 rows/batch)
  - **File:** `backend/app/api/v1/import.py`
  - **Issue:** Individual INSERT per row (slow)
  - **Fix:** Build multi-row Cypher queries
  - **Reference:** Transaction Handling, Gap #2 - Fixed Implementation
  
- [x] Add transaction timeout support
  - **File:** `backend/app/core/database.py`
  - **Issue:** Transactions can run indefinitely
  - **Fix:** Add timeout parameter to transaction() method
  - **Reference:** Transaction Handling, Gap #3
  
- [ ] Test rollback scenarios
  - **File:** `backend/tests/integration/`
  - **Tests:** Failed deletion, import validation failure
  - **Prerequisite:** Real PostgreSQL/AGE test database and integration harness (Phase 5: full FastAPI + middleware + DB test setup)
  - **Reference:** Transaction Handling, Testing Strategy
  
- [ ] Test concurrent operations
  - **File:** `backend/tests/integration/`
  - **Tests:** Concurrent deletions, race conditions (using two independent DB connections/clients)
  - **Prerequisite:** Real PostgreSQL/AGE test database with support for concurrent integration tests
  - **Reference:** Transaction Handling, Integration Tests

---

## Phase 2: Performance Optimization (Week 3-4)

**📖 Analysis Reference:** See [Performance Optimization](../analysis/02_PERFORMANCE_OPTIMIZATION.md)

### Database Indexing (HIGH Priority - 30 hours)

**Detailed guidance:** [02_PERFORMANCE_OPTIMIZATION.md - Gap #1](../analysis/02_PERFORMANCE_OPTIMIZATION.md)

- [x] Implement create_label_indices()
  - **File:** `backend/app/services/metadata.py:200-240`
  - **Issue:** No indices exist on any graph tables
  - **Fix:** Create function to generate ID, start_id, end_id indices
  - **Expected improvement:** 125x faster node lookups (250ms → 2ms)
  - **Reference:** Performance Optimization, Gap #1 - Recommended Indices
  
- [x] Create migration script for existing graphs
  - **File:** `backend/scripts/migrate_add_indices.py`
  - **Issue:** Existing graphs have no indices
  - **Fix:** Script to enumerate graphs and create indices
  - **Reference:** Performance Optimization, Implementation Checklist
  
- [ ] Test performance improvements
  - **File:** `backend/tests/performance/`
  - **Tests:** Benchmark before/after on 10k+ nodes
  - **Reference:** Performance Optimization, Success Metrics
  
- [x] Document indexing strategy
  - **File:** `docs/PERFORMANCE.md`
  - **Action:** Document which indices are created and why
  - **Reference:** Performance Optimization, Implementation Checklist

### Query Optimization (MEDIUM Priority - 20 hours)

**Detailed guidance:** [02_PERFORMANCE_OPTIMIZATION.md - Gap #2, #3, #4](../analysis/02_PERFORMANCE_OPTIMIZATION.md)

- [x] Rewrite meta-graph discovery (single query)
  - **File:** `backend/app/api/v1/graph.py`
  - **Issue:** N+1 query pattern (3N+1 queries for N edge labels)
  - **Fix:** Single Cypher aggregation query
  - **Expected improvement:** 116x faster with 100 edge labels
  - **Reference:** Performance Optimization, Gap #2 - Optimized Implementation
  
- [x] Property discovery with jsonb_object_keys()
  - **File:** `backend/app/services/metadata.py:15-79`
  - **Issue:** Samples only first N records, misses rare properties
  - **Fix:** Use PostgreSQL's jsonb_object_keys() to find ALL properties
  - **Expected improvement:** 5-10x faster, finds all properties
  - **Reference:** Performance Optimization, Gap #3 - Option 1
  
- [x] Implement property caching
  - **File:** `backend/app/services/metadata.py`
  - **Issue:** Repeated property discovery on every request
  - **Fix:** PropertyCache class with 60-minute TTL
  - **Reference:** Performance Optimization, Gap #3 - Option 2
  
- [x] Add ANALYZE after imports
  - **File:** `backend/app/api/v1/import.py`
  - **Issue:** Count estimates inaccurate without statistics
  - **Fix:** Call ANALYZE on table after import completes
  - **Reference:** Performance Optimization, Gap #4
  
- [ ] Benchmark improvements
  - **File:** `backend/tests/performance/`
  - **Tests:** Measure query times before/after
  - **Reference:** Performance Optimization, Success Metrics

---

## Phase 3: Error Handling & UX (Week 5)

**📖 Analysis Reference:** See [Error Handling](../analysis/04_ERROR_HANDLING_IMPROVEMENTS.md) and [Visualization Optimization](../analysis/06_VISUALIZATION_QUERY_OPTIMIZATION.md)

### Error Handling (MEDIUM Priority - 16 hours)

**Detailed guidance:** [04_ERROR_HANDLING_IMPROVEMENTS.md](../analysis/04_ERROR_HANDLING_IMPROVEMENTS.md)

- [x] Create graph-specific exception classes
  - **File:** `backend/app/core/errors.py`
  - **Issue:** All errors treated as generic DB_UNAVAILABLE
  - **Fix:** Add GraphConstraintViolation, GraphNodeNotFound, GraphCypherSyntaxError
  - **Reference:** Error Handling, Gap #1 - Recommended Implementation
  
- [ ] Add constraint violation detection
  - **Files:** All API endpoints
  - **Issue:** No specific handling for constraint violations
  - **Fix:** Catch psycopg.errors.UniqueViolation, ForeignKeyViolation
  - **Reference:** Error Handling, Gap #1 - Usage Example
  
- [ ] Format Cypher syntax errors
  - **File:** `backend/app/core/errors.py`
  - **Issue:** PostgreSQL errors not user-friendly
  - **Fix:** Implement format_cypher_error() function
  - **Reference:** Error Handling, Gap #3
  
- [ ] Add structured error details
  - **Files:** All API endpoints
  - **Issue:** No context for debugging
  - **Fix:** Include query, graph name, parameters in error details
  - **Reference:** Error Handling, Gap #2
  
- [ ] Update all endpoints
  - **Files:** `backend/app/api/v1/*.py`
  - **Action:** Replace generic exceptions with specific types
  - **Reference:** Error Handling, Implementation Checklist
  
- [ ] Test error messages
  - **File:** `backend/tests/`
  - **Tests:** Verify error clarity and structure
  - **Reference:** Error Handling, Implementation Checklist

### Visualization (MEDIUM Priority - 4 hours)

**Detailed guidance:** [06_VISUALIZATION_QUERY_OPTIMIZATION.md](../analysis/06_VISUALIZATION_QUERY_OPTIMIZATION.md)

- [x] Add query-time LIMIT for visualization
  - **File:** `backend/app/api/v1/query.py`
  - **Issue:** Fetches all results, then warns if too many
  - **Fix:** Add LIMIT clause to Cypher if not present
  - **Reference:** Visualization Optimization, Recommended: Query-Time LIMIT
  
- [ ] Test with large result sets
  - **File:** `backend/tests/`
  - **Tests:** Verify LIMIT applied correctly, no memory issues
  - **Reference:** Visualization Optimization, Effort Estimate

---

## Phase 4: Advanced Features (Week 6-8)

**📖 Analysis Reference:** See [AGE Features](../analysis/05_AGE_FEATURE_UTILIZATION.md) and [Path Handling](../analysis/07_PATH_HANDLING_IMPROVEMENTS.md)

### AGE Features (LOW Priority - 40 hours)

**Detailed guidance:** [05_AGE_FEATURE_UTILIZATION.md](../analysis/05_AGE_FEATURE_UTILIZATION.md)

- [ ] Research AGE algorithms
  - **Action:** Review Apache AGE documentation for available algorithms
  - **Focus:** Shortest path, aggregations, pattern matching
  - **Reference:** AGE Features, Gap #1, #2, #3
  
- [ ] Implement shortest path endpoint
  - **File:** `backend/app/api/v1/graph.py`
  - **Feature:** New endpoint for finding shortest path between nodes
  - **Implementation:** Use AGE shortestPath() function
  - **Reference:** AGE Features, Gap #1 - Implementation Example
  
- [ ] Add query templates
  - **File:** `backend/app/services/`
  - **Feature:** Pre-built query templates for common patterns
  - **Examples:** "Find influencers", "Detect cycles", "Community detection"
  - **Reference:** AGE Features, Recommended Features - #2
  
- [ ] Document advanced features
  - **File:** `docs/`
  - **Action:** User guide for AGE-specific functionality
  - **Reference:** AGE Features, Implementation Checklist

### Path Handling (LOW Priority - 12 hours)

**Detailed guidance:** [07_PATH_HANDLING_IMPROVEMENTS.md](../analysis/07_PATH_HANDLING_IMPROVEMENTS.md)

- [ ] Preserve path structure in results
  - **File:** `backend/app/services/agtype.py`
  - **Issue:** Paths flattened to separate nodes and edges
  - **Fix:** Return paths with segments, maintaining traversal order
  - **Reference:** Path Handling, Recommended: Preserve Path Structure
  
- [ ] Add path-based visualizations
  - **File:** `frontend/src/components/`
  - **Feature:** Visualize paths distinctly from general graphs
  - **Reference:** Path Handling, Benefits

---

## Phase 5: Testing & Documentation (Week 9-10)

**📖 Analysis Reference:** See [Testing Recommendations](../analysis/08_TESTING_RECOMMENDATIONS.md)

### Testing (MEDIUM Priority - 50 hours)

**Detailed guidance:** [08_TESTING_RECOMMENDATIONS.md](../analysis/08_TESTING_RECOMMENDATIONS.md)

- [ ] Full FastAPI test harness with middleware
  - **Files:** `backend/tests/conftest.py`, `app/main.py`, `app/core/middleware.py`
  - **Action:** Configure an async test client that mounts the real session, CSRF, and rate-limit middleware so currently skipped auth/session/middleware tests can run without `@pytest.mark.skip`
  - **Reference:** Testing Recommendations, #2 Integration Tests
  
- [ ] Unit tests for all new code
  - **Files:** `backend/tests/test_*.py`
  - **Coverage:** escape_identifier(), transaction wrappers, error handlers
  - **Reference:** Testing Recommendations, #1 Unit Tests
  
- [ ] Integration tests for critical flows
  - **Files:** `backend/tests/integration/`
  - **Coverage:** Complete query flows, transaction rollbacks
  - **Reference:** Testing Recommendations, #2 Integration Tests
  
- [ ] Performance tests with large graphs
  - **Files:** `backend/tests/performance/`
  - **Tests:** >100k nodes, measure execution times
  - **Reference:** Testing Recommendations, #3 Performance Tests
  
- [ ] Security test suite
  - **Files:** `backend/tests/security/`
  - **Tests:** SQL injection attempts, validation bypass scenarios
  - **Reference:** Testing Recommendations, #4 Security Tests
  
- [ ] Concurrent operation tests
  - **Files:** `backend/tests/integration/`
  - **Tests:** Parallel queries, race conditions
  - **Reference:** Testing Recommendations, Effort Estimate

### Documentation (MEDIUM Priority - 20 hours)

- [ ] Update API documentation
  - **Files:** OpenAPI specs, docstrings
  - **Action:** Document new endpoints, error types
  - **Reference:** Multiple analysis documents
  
- [ ] Create user guide for advanced features
  - **File:** `docs/USER_GUIDE.md`
  - **Content:** AGE algorithms, query templates, best practices
  - **Reference:** AGE Features documentation
  
- [ ] Document performance tuning
  - **File:** `docs/PERFORMANCE.md`
  - **Content:** Indexing strategy, caching, optimization tips
  - **Reference:** Performance Optimization document
  
- [ ] Create troubleshooting guide
  - **File:** `docs/TROUBLESHOOTING.md`
  - **Content:** Common errors, debugging tips
  - **Reference:** Error Handling document

---

## Total Effort Estimate

| Phase | Hours | Weeks | Key Deliverables |
|-------|-------|-------|------------------|
| Phase 1 (Critical) | 33 | 1-2 | Security fixes, transaction protection |
| Phase 2 (Performance) | 50 | 2 | Database indices, query optimization |
| Phase 3 (UX) | 20 | 1 | Better errors, visualization limits |
| Phase 4 (Features) | 52 | 2-3 | AGE algorithms, path handling |
| Phase 5 (Testing) | 70 | 2 | Comprehensive tests, documentation |
| **TOTAL** | **225** | **8-10** | Production-ready, optimized system |

---

## Priority Order for Minimal Viable Improvements

If resources are limited, implement in this order:

### 1. Critical Fixes (33 hours) - **MUST DO**
**Analysis:** [Security Gaps](../analysis/01_SECURITY_GAPS.md) + [Transaction Handling](../analysis/03_TRANSACTION_HANDLING.md)
   - Security gaps (10 hours)
   - Transaction protection (23 hours)
   - **Outcome:** Production-ready with no security risks, data integrity guaranteed
   
### 2. Performance (30 hours) - **HIGHLY RECOMMENDED**
**Analysis:** [Performance Optimization](../analysis/02_PERFORMANCE_OPTIMIZATION.md)
   - Database indexing (30 hours)
   - Meta-graph optimization (included in query optimization)
   - **Outcome:** 20-125x faster queries, handles large graphs

### 3. Error Handling (16 hours) - **RECOMMENDED**
**Analysis:** [Error Handling](../analysis/04_ERROR_HANDLING_IMPROVEMENTS.md)
   - Better error messages (16 hours)
   - Graph-specific exceptions (included)
   - **Outcome:** Improved debugging and user experience

**Total for MVP:** 79 hours (~2-3 weeks with 2 developers + testing)

---

## Success Metrics

Track these metrics to validate implementation success:

### Security
**Reference:** [Security Gaps](../analysis/01_SECURITY_GAPS.md)
- [ ] Zero SQL injection vulnerabilities (validated via security tests)
- [ ] All mutations wrapped in transactions (code review + tests)
- [ ] All inputs validated and escaped (automated scanning)

### Performance
**Reference:** [Performance Optimization](../analysis/02_PERFORMANCE_OPTIMIZATION.md)
- [ ] Metadata discovery <500ms for graphs with <100k nodes
- [ ] Node lookup by ID <10ms (currently 250ms)
- [ ] Meta-graph discovery <1s for any graph size (currently >3s)

### Quality
**Reference:** [Testing Recommendations](../analysis/08_TESTING_RECOMMENDATIONS.md)
- [ ] 80%+ test coverage on new code
- [ ] All error paths tested with specific test cases
- [ ] Documentation complete for all new features

---

## For AI Coding Agents

This task list is structured for automated implementation:

1. **Each task includes:**
   - Specific file paths to modify
   - Clear issue description
   - Concrete fix/implementation approach
   - Reference to detailed analysis document

2. **Recommended approach:**
   - Start with Phase 1 (security + transactions)
   - Implement tasks sequentially within each phase
   - Run tests after each task
   - Validate against success metrics

3. **Key resources:**
   - All analysis documents in `../analysis/` provide code examples
   - Testing strategies included in each analysis document
   - Performance benchmarks defined for validation

4. **Implementation order:**
   - Security fixes → Transaction protection → Indexing → Query optimization → Error handling → Advanced features → Testing
