# Sonar remediation plan (PR #16)

**Source:** SonarCloud analysis for [kotte PR #16](https://github.com/e4c5/kotte/pull/16)  
**Dashboard:** `https://sonarcloud.io/dashboard?id=e4c5_kotte&pullRequest=16`  
**Exported:** 2026-04-11 (31 open issues, total technical debt ~227 min per Sonar)

## Summary by severity

| Severity  | Count |
|-----------|-------|
| Blocker   | 0     |
| Critical  | 3     |
| Major     | 16    |
| Minor     | 12    |

---

## Critical (fix first)

1. **`backend/app/core/database/manager.py` (~L32–37, 80)** — `python:S1192`  
   **Message:** Duplicate literal `"SELECT pg_backend_pid()"` (3×).  
   **Fix:** Introduce a module-level constant, e.g. `_SQL_BACKEND_PID = "SELECT pg_backend_pid()"`, and use it in all three `cur.execute(...)` call sites.  
   **Verify:** `make test-backend` (query manager / cancellation tests if present).

2. **`backend/app/core/database/utils.py` (`split_top_level_commas`, ~L25+)** — `python:S3776`  
   **Message:** Cognitive complexity 39 (limit 15).  
   **Fix:** Extract helpers: e.g. ` _handle_quoted_char`, `_update_depth`, `_flush_part`, or split the main loop into smaller functions with clear names. Keep behavior identical; add/keep unit tests for edge cases (unbalanced brackets, quotes).  
   **Verify:** Tests covering `split_top_level_commas` and any callers.

3. **`frontend/src/hooks/useGraphExport.ts` (~L76, nesting)** — `typescript:S2004`  
   **Message:** Functions nested more than 4 levels deep (`canvas.toBlob` callback inside `img.onload` → `try` → …).  
   **Fix:** Lift inner logic into named functions (`handlePngBlob`, `renderSvgToCanvas`, etc.) or flatten with early returns so the deepest nesting is ≤4.  
   **Verify:** `make test-frontend`; manual export PNG from the UI.

---

## Major

### Python — async `timeout` parameters (`python:S7483`)

Sonar flags passing `timeout=` into async psycopg APIs. Address consistently across:

- `backend/app/core/database/connection.py` (lines ~204, 242, 267, 305, 326, 347, 365)
- `backend/app/core/database/__init__.py` (~L66)
- `backend/app/core/database/cypher.py` (~L31)

**Fix:** Remove `timeout` kwargs from async calls where the rule applies; use `asyncio.wait_for(...)`, `anyio.fail_after`, or a timeout context manager *around* the awaited operation, preserving the same effective limits as today.  
**Verify:** Connection and query tests; stress paths that used timeouts.

### Other Python

4. **`backend/tests/test_query_stream.py` (~L103)** — `python:S108`  
   **Message:** Empty / placeholder block (`pass` in async generator body).  
   **Fix:** Either implement minimal behavior the test intends (e.g. consume one chunk and assert) or replace with an explicit `pytest.skip`/commented rationale if the stub is intentional (prefer making the test meaningful).  
   **Verify:** `make test-backend`.

5. **`frontend/src/components/TabBar.tsx` (~L80–84)** — `typescript:S6848`  
   **Message:** Non-native interactive element without full a11y affordances.  
   **Fix:** Use `<button type="button">` (or `<a>` with `href`) for tab triggers, or add `role="tab"`, `tabIndex`, keyboard handlers, and focus styles to match WAI-ARIA tabs pattern.  
   **Verify:** Keyboard and screen reader smoke test on the tab bar.

6. **`frontend/src/utils/apiCache.ts` (~L12)** — `typescript:S2933`  
   **Message:** Member `cache` never reassigned — mark `readonly`.  
   **Fix:** `readonly cache = ...` (or equivalent).  
   **Verify:** `make test-frontend`.

7. **`frontend/src/components/GraphControls/FilterTab.tsx` (~L81)** — `typescript:S6479`  
   **Message:** Array index used as React `key`.  
   **Fix:** Use a stable id from data (label id, composite key) instead of `index`.  
   **Verify:** Filter UI; no unnecessary list remounts.

8. **`frontend/src/components/GraphView.tsx` (~L241)** — `typescript:S3358`  
   **Message:** Nested ternary in node styling.  
   **Fix:** Replace with a small helper, e.g. `getNodeStrokeColor(d)`, or `if`/`else` blocks.  
   **Verify:** Visual regression on node selection / path highlighting.

9. **`frontend/src/components/GraphView.tsx` (~L252)** — `typescript:S2681`  
   **Message:** Multiline `if` without braces — only first statement conditional.  
   **Fix:** Add `{ }` around the `if` body on the `.on('end', ...)` handler so all intended statements are inside the same block (matches D3 drag behavior intent).  
   **Verify:** Force layout drag-end behavior; pinned nodes.

---

## Minor

### `frontend/src/utils/graphStyles.ts`

- **`typescript:S6551` (several lines ~37, 54–55, 75, 78):** Avoid stringifying arbitrary objects; narrow types or use `String(value)` only when `value` is known primitive, or explicit `JSON.stringify` for debug.  
- **`typescript:S2486` (~L74–76):** Empty or silent `catch` — log, rethrow, or narrow the `catch` type.  
- **`typescript:S4325` (~L93):** Remove redundant type assertion.  
- **`typescript:S7735` (~L115):** Prefer positive condition or swap if/else for readability.

### Other frontend

- **`frontend/src/components/LazyRouteErrorBoundary.tsx` (~L35)** — `typescript:S7764`: Prefer `globalThis` over `window` where applicable.  
- **`frontend/src/components/GraphControls/StyleTab.tsx` (~L54, ~L118)** — `typescript:S7773`: Use `Number.parseInt` instead of global `parseInt`.  
- **`frontend/src/components/GraphView.tsx` (~L323)** — `typescript:S4325`: Remove unnecessary non-null assertion if types already allow.

### Python

- **`backend/app/core/database/connection.py` (~L391)** — `python:S2737`: `except` that only re-raises — merge with broader handling, add context, or use a bare `raise` from a narrower clause Sonar accepts.

---

## Suggested order of work

1. **GraphView L252** (S2681) — potential logic bug; quick brace fix.  
2. **Critical:** `manager.py` constant, `utils.py` refactor, `useGraphExport` flattening.  
3. **Batch:** `python:S7483` timeout pattern across DB layer.  
4. **UI polish:** TabBar a11y, FilterTab keys, graphStyles stringification/catch, remaining minors.

## Testing / verification (repo)

- Backend: `make test-backend`  
- Frontend: `make test-frontend`  
- After DB/timeout changes: run integration tests that exercise pooled connections and streaming queries.

---

*Generated from Sonar issues API export; line numbers refer to the analyzed PR branch and may shift slightly after edits.*

---

## Re-export — 2026-04-11T15:01:02Z

**API:** `https://sonarcloud.io/api/issues/search?componentKeys=e4c5_kotte&resolved=false&ps=500&additionalFields=_all&pullRequest=16`

Counts unchanged: **31** open issues (Critical 3, Major 16, Minor 12), ~227 min estimated debt.

**Spot-check vs. current workspace**

- **`backend/app/core/database/manager.py`:** This tree already has `_SQL_BACKEND_PID = "SELECT pg_backend_pid()"` and uses it in `execute` calls. If PR #16 matches this code, **`python:S1192` should clear on the next Sonar analysis**; if the PR branch is behind, applying that constant still addresses the finding.
- **`frontend/src/components/GraphView.tsx` (~L251–252):** The D3 drag `.on('end', …)` handler still uses a single-line `if` with multiple statements — **`typescript:S2681`** (brace / conditional execution) still applies until refactored.
- **`backend/tests/test_query_stream.py` (~L103):** Async generator body still contains **`pass`** — **`python:S108`** still applies.

Raw export used for this run was removed after analysis (`sonar-context.json` next to the analyze script).

---

## Re-export — 2026-04-11T15:15Z (API: 5 open issues)

**Source:** `analyze_sonar.py` (latest open PR → SonarCloud PR #16)  
**API:** `https://sonarcloud.io/api/issues/search?componentKeys=e4c5_kotte&resolved=false&ps=500&additionalFields=_all&pullRequest=16`  
**Totals:** 5 open issues, **32 min** estimated debt (`effortTotal`).

### Summary by severity

| Severity  | Count |
|-----------|-------|
| Critical  | 1     |
| Major     | 0     |
| Minor     | 4     |

---

### Duplications and repeated patterns (focus)

Sonar’s **“Duplicated blocks”** metric is separate from **Issues**; this export does not include duplication-density rows. Within the **issue list**, the clearest **duplication-related** work is:

1. **`typescript:S6551` ×3 in one file** (`frontend/src/utils/graphStyles.ts`, lines **37**, **68**, **83**)  
   Same rule, same maintenance theme: **coercing `unknown` values to strings** in a way that can produce `[object Object]`.

   - **L37:** `Number.parseFloat(String(propValue))` — if `propValue` were ever a non-primitive object, stringification is wrong before `parseFloat`.
   - **L68 / L83:** In `getDescriptivePropertyValue`, after the `typeof value === 'object'` branch, the `else` path still uses `String(value)`; TypeScript may not prove exhaustiveness, so the rule fires.

   **Remediation (deduplicate behavior):** Add a single helper, e.g. `coerceNumericFromProperty(value: unknown): number | null` (only accept `number` or string-ish inputs; for objects return `null` or route through `safeStringify` + parse if that is intentional). For caption primitives, add `formatPrimitiveForCaption(value: unknown): string` that handles `string | number | boolean | bigint` explicitly and uses `safeStringify` for objects. Then **replace the three call sites** so string coercion is not repeated three ways. This addresses all three findings in one refactor and reduces future copy-paste.

2. **`python:S3776` on `split_top_level_commas`** (`backend/app/core/database/utils.py`, **~L50**)  
   Cognitive complexity **26** (limit 15). The function’s main loop contains **near-duplicate control flow** for single-quoted vs double-quoted string modes (`in_sq` / `in_dq` blocks mirror each other, as do the branches that enter those modes).

   **Remediation:** Extract small helpers, e.g. `_handle_inside_single_quote`, `_handle_inside_double_quote`, or a parameterized `_handle_quote_state(...)`, so the **same logic is not written twice**. That directly targets **structural duplication** and should lower complexity enough to satisfy the rule. Keep behavior identical; extend tests for unbalanced quotes and nested delimiters if coverage is thin.

---

### Other issues in this export

| File | Line | Rule | Message / fix |
|------|------|------|----------------|
| `frontend/src/utils/graphStyles.ts` | 103 | `typescript:S4325` | Redundant assertion on `node.properties as Record<string, unknown>` — remove or narrow types so the cast is unnecessary. |

---

### Verification

- Frontend: `make test-frontend` after `graphStyles.ts` helper extraction.
- Backend: `make test-backend` after `split_top_level_commas` refactor (any tests covering `split_top_level_commas` / Cypher column parsing).

**Note:** An earlier snapshot listed **31** open issues on the same PR; this run returned **5**, so many findings may already be **resolved or outdated** on SonarCloud. For **duplicated lines %** and **duplicated blocks**, check the Sonar **Measures** / **Duplications** tab for component `e4c5_kotte` on PR 16; those values are not in `issues/search`.
