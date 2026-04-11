# PR #16 — Actionable review items (verified against local tree)

This file lists **confirmed** gaps that still need code or documentation work. Items marked “already addressed on branch” were verified in the workspace and are handled via review replies instead.

---

## 1. `DatabaseConnection.get_query_pid` drops `query_text`

- **Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3067966636 (and duplicate thread on same fix: discussion around `get_query_pid` in `__init__.py`)
- **File & context:** `backend/app/core/database/__init__.py` — `get_query_pid` ~55–57
- **Finding:** Facade accepts `query_text` but calls `self._query_manager.get_query_pid()` with no args; `QueryManager.get_query_pid` supports SQL filtering.
- **Original suggestion:** Forward `query_text` to the manager.
- **Verified plan:**
  1. Change to `return await self._query_manager.get_query_pid(query_text)`.
  2. Add or extend a unit test (mock `QueryManager`) asserting the manager receives the same `query_text`.
- **Testing strategy:** `make test-backend` — target `backend/tests` for database facade / manager if present; add focused test in `test_database.py` or new small test module.
- **Risks:** None if signature matches `QueryManager.get_query_pid`.

---

## 2. Security headers: dev docs, CSP, and HSTS

- **Comment URLs:** e.g. https://github.com/e4c5/kotte/pull/16#discussion_r3067966874 (main), middleware threads on CSP and HSTS
- **Files:** `backend/app/main.py` (~101–102), `backend/app/core/middleware.py` (`SecurityHeadersMiddleware`)
- **Finding:** Middleware runs unconditionally. Strict CSP blocks Swagger/ReDoc CDN assets in development; HSTS is tied to `not settings.debug`, which is still true in default `development` (so HSTS can apply on plain HTTP dev servers).
- **Verified plan:**
  1. Gate `SecurityHeadersMiddleware` behind `settings.environment == "production"` **or** add a dev-specific CSP that allows Swagger UI / ReDoc CDN origins when `settings.environment == "development"` and docs routes are enabled.
  2. Set HSTS only when `settings.environment == "production"` and `request.url.scheme == "https"` (align with CodeAnt suggestion).
  3. Update `backend/tests/test_security_headers.py` expectations to match the chosen policy.
- **Testing strategy:** `make test-backend`; manual smoke: open `/api/docs` and `/api/redoc` in development after changes.
- **Risks:** Production behavior must remain strict; avoid widening CSP in production.

---

## 3. Metadata cache invalidation: validation and key safety

- **Comment URLs:** threads on `backend/app/services/metadata.py` (invalidate helper, `create_label_indices`, `analyze_table`)
- **Files:** `backend/app/services/metadata.py`
- **Finding:** `invalidate_property_metadata_cache` builds cache keys from `graph_name` / `label_name` without re-validating; some call sites pass validated names, others could be inconsistent; prefix-based `clear(prefix=f"props:{graph_name}")` can theoretically collide with graph names that share prefixes (edge case).
- **Verified plan:**
  1. At the start of `invalidate_property_metadata_cache`, call `validate_graph_name` and, when `label_name` is set, `validate_label_name`.
  2. Ensure every call site passes validated graph/label identifiers (use the same variables as SQL paths, e.g. `validated_graph_name` from callers).
  3. Consider delimiter-bound keys (e.g. ensure prefix ends with `:` and graph name is validated) to reduce accidental cross-graph clears.
- **Testing strategy:** `make test-backend`; extend `test_metadata.py` for invalid names and cache key behavior.
- **Risks:** Over-invalidating cache is safer than under-invalidating; watch test performance.

---

## 4. CSV import: post-commit cache invalidation and analysis

- **Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r… (csv_importer ~289–292)
- **File:** `backend/app/api/v1/csv_importer.py`
- **Finding:** After successful commit, `invalidate_property_metadata_cache` / `analyze_table` failures can fail the HTTP response even though data is committed.
- **Verified plan:** Wrap post-commit cache/metadata calls in try/except; log warnings with graph/label context; do not fail the import response if DB work succeeded.
- **Testing strategy:** Mock `invalidate_property_metadata_cache` to raise; assert API still returns completed import.
- **Risks:** Operators rely on logs to spot cache drift if invalidation fails.

---

## 5. `QueryManager.get_backend_pid` vs pool semantics

- **File:** `backend/app/core/database/manager.py`
- **Finding:** Uses a **pooled** connection; PID may not match a specific “current” session if callers assume sticky backend PID.
- **Verified plan:** Document behavior, or expose PID via the same connection used for the active transaction if product requires it; add tests aligned with intended contract.
- **Testing strategy:** Integration tests with real DB if applicable.
- **Risks:** Changing to long-lived connection semantics affects pooling.

---

## 6. `execute_query` / `execute_command` rollback when `conn` is supplied

- **File:** `backend/app/core/database/connection.py` (`_execute_query_on_conn`, `_execute_command_on_conn`)
- **Finding:** On error, code calls `conn.rollback()`, which rolls back the **entire** outer transaction when `conn` is shared (e.g. CSV import batch inside `transaction()`).
- **Verified plan:** Only rollback when this layer owns the transaction, or document that callers must not mix transactional and non-transactional use; alternatively catch and re-raise without rollback when `conn` is passed (if psycopg/transaction context already handles it).
- **Testing strategy:** Regression test importing CSV or nested transaction scenario.
- **Risks:** Removing rollback could leave connection in failed state if not coordinated with psycopg transaction manager.

---

## 7. Pool initialization failure cleanup

- **File:** `backend/app/core/database/connection.py` — `connect()`
- **Finding:** If `AsyncConnectionPool` is created but `open()`/`wait()` fails, ensure `_pool` and any tasks are cleared consistently (avoid zombie metrics task or partial pool).
- **Verified plan:** Use try/finally or explicit cleanup on failure path; verify with a test that forces connection failure.
- **Testing strategy:** Mock pool open to raise; assert no leaked task references.
- **Risks:** Low if structured as try/except/finally.

---

## 8. Frontend: lazy routes without `ErrorBoundary`

- **File:** `frontend/src/App.tsx`
- **Finding:** Lazy chunks that fail to load will error the whole tree.
- **Verified plan:** Add a small `ErrorBoundary` (or route-level error element) around `Suspense` children with a retry/fallback UI.
- **Testing strategy:** `make test-frontend`; optional manual simulation of failed chunk.
- **Risks:** Keep fallback UI consistent with existing styling.

---

## 9. Frontend: `FilterTab` — optional label vs validation

- **File:** `frontend/src/components/GraphControls/FilterTab.tsx` (~27–36)
- **Finding:** Placeholder says “Label (optional)” but `handleAddFilter` requires `newFilter.label`.
- **Verified plan:** Require property + value (trimmed); treat label as optional; adjust display of active filters when label empty.
- **Testing strategy:** Component/unit tests if present; manual add filter without label.
- **Risks:** Store/query code must accept empty label if that is valid for `graphStore`.

---

## 10. Frontend: `useGraphExport` — stabilize `exportToPNG`

- **File:** `frontend/src/hooks/useGraphExport.ts`
- **Finding:** New function identity every render can retrigger `useEffect` in `GraphView` that depends on `exportToPNG`.
- **Verified plan:** Wrap `exportToPNG` in `useCallback` with deps `[svgRef, width, height]`.
- **Testing strategy:** `make test-frontend`; smoke export from graph view.
- **Risks:** Ensure deps match everything read inside the callback.

---

## 11. Frontend: API client cache invalidation on mutations

- **File:** `frontend/src/services/api.ts` (~102–107)
- **Finding:** Only clears graph cache when URL includes `/graph`; query execution and other mutations may leave stale cached GETs.
- **Verified plan:** Expand rules (e.g. invalidate `/query` or broader prefix) per API surface, or key cache by method+url strictly to avoid stale reads.
- **Testing strategy:** Unit/integration tests for cache helper behavior.
- **Risks:** Over-invalidation increases load; tune TTL/prefixes.

---

## 12. Config: pool size validation

- **File:** `backend/app/core/config.py`
- **Finding:** `db_pool_min_size`, `db_pool_max_size`, `db_pool_max_idle` can be misconfigured at runtime.
- **Verified plan:** Pydantic `Field` constraints and `@model_validator` for `min <= max`.
- **Testing strategy:** `backend/tests/test_config.py`.
- **Risks:** None for valid configs.

---

## 13. Credentials: audit log for dev encryption key

- **File:** `backend/app/core/credentials.py`
- **Finding:** When falling back to dev key, should emit `SECURITY:` structured log per project conventions.
- **Verified plan:** Add `logger.warning("SECURITY: ...", extra={...})` alongside existing `warnings.warn`.
- **Testing strategy:** Adjust or add tests if logging is asserted.
- **Risks:** Do not log secrets.

---

## 14. Structured logging: default `request_id`

- **File:** `backend/app/core/logging.py` — `JSONFormatter`
- **Finding:** Base payload omits `request_id`; it only appears if injected as `extra`. Request tracing is easier if the key is always present (`null` when absent).
- **Verified plan:** Add `"request_id": getattr(record, "request_id", None)` (or from `record.__dict__` merge) to `log_data`.
- **Testing strategy:** Log capture test.
- **Risks:** None.

---

## 15. `errors.py`: portability of 422 constant

- **File:** `backend/app/core/errors.py`
- **Finding:** `HTTP_422_UNPROCESSABLE_CONTENT` exists in current deps; older Starlette might not (CodeAnt concern).
- **Verified plan:** If supporting a wider version range, use `HTTP_422_UNPROCESSABLE_ENTITY` or `422` literal; otherwise document minimum Starlette version.
- **Testing strategy:** `tests/test_errors.py` already covers `GraphCypherSyntaxError`.
- **Risks:** Low if minimum versions are pinned.

---

## 16. Cypher / SQL composition (CodeRabbit refactor threads)

- **Files:** `backend/app/core/database/cypher.py` (and related)
- **Finding:** Review comments suggested aligning with `psycopg.sql` / safer composition; verify each dynamic fragment uses validated identifiers and parameters.
- **Verified plan:** Audit `cypher.py` for string concatenation; refactor hot spots to composable SQL with bound parameters per project security rules.
- **Testing strategy:** Existing cypher/database tests.
- **Risks:** Regression on AGE `cypher()` call shapes.

---

## 17. Documentation: architecture sync

- **File:** `docs/BACKLOG.md` vs `docs/ARCHITECTURE.md` / `docs/ADVANCED_FEATURES.md`
- **Finding:** Large refactor should be reflected in architecture docs.
- **Verified plan:** Update architecture docs to describe modular DB layer, caching, middleware, and frontend lazy loading — only where this PR introduces durable behavior.
- **Testing strategy:** N/A (docs).
- **Risks:** Stale diagrams; keep edits proportional to merged code.

---

## 18. `.agents` PR review script (path + robustness)

- **Context:** Review threads reference `.agents/skill/respond-pr-review/scripts/analyze_pr.py`. Canonical location in this repo is `.agents/skills/respond-pr-review-comments/scripts/analyze_pr.py`.
- **Finding:** Pagination (`first: 50`) can truncate large PRs; append vs overwrite policy for generated files; optional further hardening from CodeRabbit.
- **Verified plan:**
  1. Ensure the PR ships a single canonical path (remove dead `.agents/skill/...` if duplicated).
  2. Add GraphQL pagination cursors for threads/comments if PRs can exceed 50 items.
  3. Keep subprocess `timeout=` on all `gh` calls (already present locally).
- **Testing strategy:** Run script against this PR after changes.
- **Risks:** GitHub API rate limits when paginating.

---

## Issue / summary comments (no thread resolution)

Comments such as CodeAnt/Viper/Sonar/CodeRabbit summaries (`#issuecomment-*`) are informational. No code change required unless a bullet is duplicated above.
