# Implementation Checklist

Complete task list for all identified improvements.

---

## Phase 1: Critical Security & Data Integrity (Week 1-2)

### Security Fixes (HIGH Priority - 10 hours)
- [ ] Fix unvalidated graph_name in graph.py:221
- [ ] Implement escape_identifier() utility
- [ ] Apply escaping to metadata.py (3 locations)
- [ ] Apply escaping to graph.py:272
- [ ] Apply escaping to import_csv.py (2 locations)
- [ ] Add unit tests for escape_identifier()
- [ ] Security review of all f-string queries

### Transaction Protection (HIGH Priority - 23 hours)
- [ ] Wrap node deletion in transaction
- [ ] Add deletion verification
- [ ] CSV pre-validation implementation
- [ ] Move graph/label creation into transaction
- [ ] Implement batch insertion (1000 rows/batch)
- [ ] Add transaction timeout support
- [ ] Test rollback scenarios
- [ ] Test concurrent operations

---

## Phase 2: Performance Optimization (Week 3-4)

### Database Indexing (HIGH Priority - 30 hours)
- [ ] Implement create_label_indices()
- [ ] Add auto-index on metadata request
- [ ] Create migration script for existing graphs
- [ ] Test performance improvements
- [ ] Document indexing strategy

### Query Optimization (MEDIUM Priority - 20 hours)
- [ ] Rewrite meta-graph discovery (single query)
- [ ] Property discovery with jsonb_object_keys()
- [ ] Implement property caching
- [ ] Add ANALYZE after imports
- [ ] Benchmark improvements

---

## Phase 3: Error Handling & UX (Week 5)

### Error Handling (MEDIUM Priority - 16 hours)
- [ ] Create graph-specific exception classes
- [ ] Add constraint violation detection
- [ ] Format Cypher syntax errors
- [ ] Add structured error details
- [ ] Update all endpoints
- [ ] Test error messages

### Visualization (MEDIUM Priority - 4 hours)
- [ ] Add query-time LIMIT for visualization
- [ ] Test with large result sets

---

## Phase 4: Advanced Features (Week 6-8)

### AGE Features (LOW Priority - 40 hours)
- [ ] Research AGE algorithms
- [ ] Implement shortest path endpoint
- [ ] Add query templates
- [ ] Document advanced features

### Path Handling (LOW Priority - 12 hours)
- [ ] Preserve path structure in results
- [ ] Add path-based visualizations

---

## Phase 5: Testing & Documentation (Week 9-10)

### Testing (MEDIUM Priority - 50 hours)
- [ ] Unit tests for all new code
- [ ] Integration tests for critical flows
- [ ] Performance tests with large graphs
- [ ] Security test suite
- [ ] Concurrent operation tests

### Documentation (MEDIUM Priority - 20 hours)
- [ ] Update API documentation
- [ ] Create user guide for advanced features
- [ ] Document performance tuning
- [ ] Create troubleshooting guide

---

## Total Effort Estimate

| Phase | Hours | Weeks |
|-------|-------|-------|
| Phase 1 (Critical) | 33 | 1-2 |
| Phase 2 (Performance) | 50 | 2 |
| Phase 3 (UX) | 20 | 1 |
| Phase 4 (Features) | 52 | 2-3 |
| Phase 5 (Testing) | 70 | 2 |
| **TOTAL** | **225** | **8-10** |

---

## Priority Order for Minimal Viable Improvements

If resources are limited, implement in this order:

1. **Critical Fixes** (33 hours)
   - Security gaps
   - Transaction protection
   
2. **Performance** (30 hours)
   - Database indexing
   - Meta-graph optimization

3. **Error Handling** (16 hours)
   - Better error messages
   - Graph-specific exceptions

**Total for MVP:** 79 hours (~2-3 weeks with testing)

---

## Success Metrics

### Security
- [ ] Zero SQL injection vulnerabilities
- [ ] All mutations in transactions
- [ ] All inputs validated and escaped

### Performance
- [ ] Metadata discovery <500ms
- [ ] Node lookup <10ms
- [ ] Meta-graph discovery <1s

### Quality
- [ ] 80%+ test coverage
- [ ] All error paths tested
- [ ] Documentation complete
