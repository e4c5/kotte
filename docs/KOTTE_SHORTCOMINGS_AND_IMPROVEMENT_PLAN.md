# Kotte Shortcomings and Improvement Plan

## Scope
This review is based on:
- `kotte/AGENTS.md`
- backend API/core/services code
- frontend workspace/query/graph UI code
- project packaging and CI workflow

## Key Shortcomings

1. Visualization result capping is computed but not applied end-to-end.
- Backend computes `cypher_to_execute` but executes `request.cypher`.
- File refs: `kotte/backend/app/api/v1/query.py:82`, `kotte/backend/app/api/v1/query.py:159`
- Frontend request model/store does not pass `for_visualization`.
- File refs: `kotte/frontend/src/services/query.ts:7`, `kotte/frontend/src/stores/queryStore.ts:234`

2. Streaming query lifecycle has gaps.
- If user query already includes `LIMIT/SKIP`, streaming degrades to one chunk.
- Active stream queries are registered but not explicitly unregistered on completion/error/cancel.
- File refs: `kotte/backend/app/api/v1/query_stream.py:99`, `kotte/backend/app/api/v1/query_stream.py:203`

3. Auth/session and rate limiting are MVP-level for production.
- Hardcoded `admin` user and SHA-256 password hashing.
- In-memory sessions (single instance only).
- User rate limiting likely ineffective due request scope lookup pattern.
- File refs: `kotte/backend/app/services/user.py:18`, `kotte/backend/app/core/auth.py:22`, `kotte/backend/app/core/middleware.py:184`

4. Query logging may expose sensitive details.
- Logs full Cypher and bind params at info level.
- File refs: `kotte/backend/app/core/database.py:321`, `kotte/backend/app/api/v1/query.py:147`

5. Dependency/packaging inconsistency.
- `pyproject.toml` misses runtime packages present in `requirements.txt` (`itsdangerous`, `prometheus-client`).
- File refs: `kotte/backend/pyproject.toml:10`, `kotte/backend/requirements.txt:10`

6. CI coverage is too limited.
- GitHub Actions currently checks docs only; no backend/frontend test/lint/build workflow.
- File ref: `kotte/.github/workflows/docs.yml:1`

7. Product fit gap for Antikythera Knowledge Graph use case.
- UX and templates are generic graph exploration; weak first-class support for `CodeElement`/`nodeType` and edge semantics (`CALLS`, `USES`, etc.).
- File refs: `kotte/frontend/src/components/MetadataSidebar.tsx:59`, `kotte/backend/app/services/query_templates.py:9`

8. Metadata endpoint can become expensive on large graphs.
- Per-label loops plus per-property stats fan out into many DB calls.
- File ref: `kotte/backend/app/api/v1/graph.py:116`

9. Mutations are easy to trigger for analysis-centric workflows.
- Node deletion exposed in API and UI while safe mode defaults off.
- File refs: `kotte/backend/app/api/v1/graph_delete_node.py:24`, `kotte/frontend/src/components/NodeContextMenu.tsx:126`, `kotte/backend/app/core/config.py:31`

## Improvement Plan

### Phase 0: Correctness fixes (1-2 days)
- Execute `cypher_to_execute` instead of `request.cypher` for visualization-limited runs.
- Add `for_visualization` in frontend request type and send true for graph-mode execution.
- Ensure streaming queries are always unregistered from `query_tracker` on all exit paths.
- Add focused tests for these three behaviors.

### Phase 1: KnowledgeGraph-first UX (3-5 days)
- Add built-in templates tailored to code graphs:
  - callers/callees
  - class hierarchy
  - interface implementations
  - type members
  - lambda/method-reference relationships
  - unresolved (`resolution='partial'`) diagnostics
- Add node context actions for code exploration paths.
- Add sidebar pivots/filters by `nodeType` and edge type.

### Phase 2: Performance/scalability (3-5 days)
- Optimize metadata aggregation to reduce N+1 query patterns.
- Improve streaming pagination strategy for queries with existing `LIMIT/SKIP`.
- Add query guardrails for high-cost traversals (depth/result caps with clear UX feedback).

### Phase 3: Security hardening (3-5 days)
- Replace hardcoded user model with real user store and strong password hashing (bcrypt/argon2).
- Move sessions and rate limiting to Redis for multi-instance deployments.
- Redact query logs by default; configurable debug-level full logging only.
- Introduce an analysis/read-only profile that hides destructive UI operations.

### Phase 4: Delivery reliability (2-3 days)
- Unify dependency management between `pyproject.toml` and requirements files.
- Add CI workflows for backend lint/type/test and frontend lint/test/build.
- Add a smoke integration workflow against a sample Antikythera graph fixture.

## Suggested Execution Order
1. Phase 0 (correctness)
2. Phase 1 (KnowledgeGraph usability)
3. Phase 4 (CI/dependency reliability)
4. Phase 2 and Phase 3 in parallel where feasible

## Notes
- Local backend tests were not executed successfully in this environment due missing local dependencies/plugins.
- Before implementing deeper changes, run `make install-backend` and `make test-backend` in project-standard environment.
