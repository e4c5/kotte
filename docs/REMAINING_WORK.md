# Remaining Work Summary

## ✅ Completed (Major Features)

### Critical Security & Authentication
- ✅ Authentication system (login/logout endpoints)
- ✅ Encrypted credential storage (AES-256-GCM with PBKDF2)
- ✅ Connection storage service (encrypted JSON file)
- ✅ Saved connection endpoints (CRUD operations)
- ✅ Frontend saved connections UI
- ✅ Security hardening (SQL injection fixes, CSRF protection, rate limiting)
- ✅ Input validation (graph names, label names, query length)
- ✅ Query cancellation (with PostgreSQL PID tracking and timeout)

### High Priority Features
- ✅ Oversized result handling (visualization caps, auto-switch to table view)
- ✅ Health check endpoints (`/health`, `/ready`)
- ✅ Testing infrastructure (unit tests, integration tests with Docker Compose)
- ✅ Neighborhood expansion (backend endpoint + frontend UI)

---

## 🚧 Remaining Work

### Medium Priority Features

#### 1. Edge Width Mapping
**Priority: MEDIUM**  
**Estimated Effort: 1 day**

**Tasks:**
- Add property statistics to metadata endpoint (return numeric property ranges for edges)
- Add edge width mapping control to GraphControls component
- Implement d3 scale mapping (linear or log scale)
- Update GraphView to apply mapped widths to edges

**Files to modify:**
- `backend/app/models/graph.py` (add property stats to metadata response)
- `backend/app/services/metadata.py` (calculate property ranges)
- `frontend/src/components/GraphControls.tsx` (add width mapping UI)
- `frontend/src/stores/graphStore.ts` (add width mapping state)
- `frontend/src/components/GraphView.tsx` (apply width mapping to edges)

---

#### 2. Node Deletion
**Priority: MEDIUM**  
**Estimated Effort: 1-2 days**

**Tasks:**
- Add `DELETE /api/v1/graphs/{graph}/nodes/{id}` endpoint
- Accept `detach` parameter (default: false) for deleting with relationships
- Execute Cypher: `MATCH (n) WHERE id(n) = $id [DETACH] DELETE n`
- Add "Delete Node" option to context menu
- Add confirmation dialog
- Refresh graph after deletion

**Files to modify:**
- `backend/app/api/v1/graph.py` (add delete endpoint)
- `backend/app/models/graph.py` (add delete request/response models)
- `frontend/src/components/NodeContextMenu.tsx` (add delete action)
- `frontend/src/services/graph.ts` (add delete API call)
- `frontend/src/components/GraphView.tsx` (handle deletion and refresh)

---

#### 3. Result Streaming
**Priority: MEDIUM**  
**Estimated Effort: 2-3 days**

**Tasks:**
- Implement FastAPI StreamingResponse for large result sets
- Stream results in chunks (e.g., 1000 rows at a time)
- Support pagination with cursor/offset
- Add pagination controls to TableView
- Implement virtual scrolling or "Load more" button
- Update query store to handle paginated results

**Files to modify:**
- `backend/app/api/v1/query.py` (add streaming endpoint or pagination)
- `backend/app/models/query.py` (add pagination request/response models)
- `frontend/src/components/TableView.tsx` (add pagination UI)
- `frontend/src/stores/queryStore.ts` (add pagination state)
- `frontend/src/services/query.ts` (add pagination support)

---

#### 4. PNG Export
**Priority: MEDIUM**  
**Estimated Effort: 1 day**

**Tasks:**
- Add export button to graph view
- Implement SVG to PNG conversion (client-side using html2canvas or similar)
- Add download functionality
- Optionally: server-side PNG generation endpoint

**Files to modify:**
- `frontend/src/components/GraphView.tsx` (add export function)
- `frontend/src/pages/WorkspacePage.tsx` (add export button)
- Optionally: `backend/app/api/v1/query.py` (add export endpoint)

---

### Observability & Production Readiness

#### 5. Prometheus Metrics
**Priority: MEDIUM** (Required for Production)  
**Estimated Effort: 1-2 days**

**Tasks:**
- Add Prometheus metrics endpoint (`/metrics`)
- Track query latency (histogram)
- Track error rates (counter)
- Track active sessions (gauge)
- Track connection attempts (counter)
- Track query execution counts

**Files to modify:**
- `backend/app/core/metrics.py` (new - metrics collection)
- `backend/app/api/v1/health.py` (add metrics endpoint)
- `backend/app/core/middleware.py` (add metrics collection hooks)
- `backend/requirements.txt` (add `prometheus-client`)

---

### Low Priority / Polish Features

#### 6. Settings Persistence
**Priority: LOW**  
**Estimated Effort: 1 day**

**Tasks:**
- Create settings store with localStorage persistence
- Save theme preference
- Save layout defaults
- Save data limits/visualization caps
- Load settings on app start

**Files to modify:**
- `frontend/src/stores/settingsStore.ts` (new)
- `frontend/src/components/SettingsModal.tsx` (new)
- `frontend/src/pages/WorkspacePage.tsx` (integrate settings)

---

#### 7. Multi-Result Panels
**Priority: LOW**  
**Estimated Effort: 2-3 days**

**Tasks:**
- Refactor WorkspacePage to support tabbed interface
- Each tab has its own query, graph/table view
- Add close, refresh, pin actions for tabs
- Support multiple concurrent query results

**Files to modify:**
- `frontend/src/pages/WorkspacePage.tsx` (refactor to tabs)
- `frontend/src/components/ResultTab.tsx` (new)
- `frontend/src/stores/queryStore.ts` (support multiple results)

---

#### 8. Accessibility
**Priority: LOW**  
**Estimated Effort: 2 days**

**Tasks:**
- Add ARIA labels to all interactive elements
- Add roles and descriptions
- Implement keyboard navigation (Tab order, shortcuts)
- Ensure WCAG AA contrast compliance
- Add high contrast theme option

**Files to modify:**
- All frontend components (add ARIA attributes)
- `frontend/src/components/GraphView.tsx` (keyboard navigation)
- `frontend/src/components/QueryEditor.tsx` (keyboard shortcuts)
- Global styles (contrast compliance)

---

## 📊 Summary by Priority

### Medium Priority (Production Features)
1. **Edge Width Mapping** - 1 day
2. **Node Deletion** - 1-2 days
3. **Result Streaming** - 2-3 days
4. **PNG Export** - 1 day
5. **Prometheus Metrics** - 1-2 days

**Total: ~7-9 days**

### Low Priority (Polish)
6. **Settings Persistence** - 1 day
7. **Multi-Result Panels** - 2-3 days
8. **Accessibility** - 2 days

**Total: ~5-6 days**

---

## 🎯 Recommended Next Steps

1. **Prometheus Metrics** (observability-1) - Critical for production monitoring
2. **Edge Width Mapping** (edge-width-1) - Quick win, enhances visualization
3. **Node Deletion** (node-deletion-1) - Useful graph manipulation feature
4. **Result Streaming** (result-streaming-1) - Important for large datasets
5. **PNG Export** (png-export-1) - Quick feature for sharing visualizations

Then move to polish features (settings, multi-panels, accessibility) as time permits.

---

## 📝 Notes

- All critical security features are complete
- All high-priority production features are complete
- Testing infrastructure is in place with good coverage
- The remaining work focuses on enhanced features and polish
- The system is production-ready for core functionality

