# Sonar Remediation Plan

Date: 2026-04-13  
Source: https://sonarcloud.io/project/issues?issueStatuses=OPEN&id=e4c5_kotte

## Summary

- Total open issues: 278
- By severity:
  - BLOCKER: 60
  - CRITICAL: 29
  - MAJOR: 84
  - MINOR: 105
- By type:
  - CODE_SMELL: 245
  - VULNERABILITY: 29
  - BUG: 4

## Duplication Overview

- Project duplication metrics:
  - duplicated lines density: 0.7%
  - duplicated lines: 162
  - duplicated blocks: 6
  - duplicated files: 4
- New-code duplication metrics are 0 (no new duplicated blocks/lines in the quality period).

High-signal duplication blocks from Sonar export:
- `backend/app/services/agtype.py`: duplicated block at line 449, size 19 and line 470, size 19.
- `frontend/src/components/GraphView.tsx`: duplicated block at line 890, size 33 and line 941, size 33.
- Cross-file duplicate between `backend/app/api/v1/csv_importer.py` (line 295, size 29) and `backend/app/api/v1/import_csv.py` (line 251, size 29).

Note: current repo no longer contains `backend/app/api/v1/import_csv.py` and current `frontend/src/components/GraphView.tsx` has fewer lines than Sonar-reported offsets, so those two need a quick Sonar refresh/reindex before line-accurate cleanup.

## Prioritized Action List

1. **[BLOCKER] FastAPI dependency injection type hints (`python:S8410`)**
- Scope: 36 findings across API routers (`graph.py`, `csv_importer.py`, `connections.py`, `query.py`, `session.py`, `auth.py`, `health.py`, `query_stream.py`, `graph_delete_node.py`).
- Verified in repo: many signatures still use `param: Type = Depends(...)`.
- Fix approach:
  - Replace with `Annotated` style consistently, for example:
    - `db_conn: Annotated[DatabaseConnection, Depends(get_db_connection)]`
    - `session: Annotated[dict, Depends(get_session)]`
  - Add `from typing import Annotated` where missing.
- Verification:
  - Run backend tests and lint/type checks after bulk refactor.

2. **[BLOCKER] Redundant `response_model` with return annotation (`python:S8409`)**
- Scope: 23 findings, concentrated in API route decorators.
- Verified in repo: route decorators still include `response_model=...` while functions also return typed response models.
- Fix approach:
  - Keep one source of truth per endpoint:
    - Prefer return annotations on handler signatures.
    - Remove redundant `response_model=...` where equivalent.
  - Retain explicit `status_code=` where needed.
- Verification:
  - Run FastAPI schema smoke check (OpenAPI generation) and route tests.

3. **[BLOCKER] Middleware ordering: CORS should be last-added (`python:S8414`)**
- Scope: 1 finding in app setup.
- Verified in repo: `CORSMiddleware` is currently added before several middlewares in `backend/app/main.py`.
- Fix approach:
  - Reorder `app.add_middleware(...)` calls so CORS is added last according to Sonar/FastAPI guidance.
  - Re-validate comments in file to match actual execution order.
- Verification:
  - Run API integration tests covering CORS and session/csrf interactions.

4. **[CRITICAL] Reduce cognitive complexity in AGE parsing service (`python:S3776`)**
- Scope: multiple high-complexity functions in `backend/app/services/agtype.py` (including one very high-complexity function).
- Verified in repo: parser/extraction logic is deeply nested and branch-heavy.
- Fix approach:
  - Split into focused helpers by concern:
    - string normalization/parsing
    - node/edge/path classification
    - graph element extraction and dedupe
  - Replace repeated nested conditionals with small strategy helpers and early returns.
- Verification:
  - Add/extend unit tests for parser edge cases before and after refactor.

### Cognitive Complexity in AGE Parsing Service (S3776)

#### Analysis:
The following functions in `backend/app/services/agtype.py` exhibit high cognitive complexity:

1. **`parse()`**:
   - Handles multiple cases for parsing `agtype` values.
   - Contains nested conditionals and exception handling.
   - Complexity arises from handling various data types and formats.

2. **`_parse_dict()`**:
   - Checks for vertex, edge, and path structures.
   - Complexity stems from multiple conditional checks and recursive parsing.

3. **`_parse_edge()`**:
   - Processes edges with various key formats.
   - Complexity due to repetitive checks for different key names.

4. **`_build_path_structure()`**:
   - Constructs path structures from parsed elements.
   - Complexity arises from nested loops and conditionals.

5. **`extract_graph_elements()`**:
   - Extracts nodes, edges, and paths from query results.
   - Complexity due to nested loops, conditionals, and inline helper functions.

#### Recommendations:
- Refactor large functions into smaller, reusable components.
- Use helper functions to handle repetitive tasks like key extraction.
- Simplify nested conditionals by using early returns or guard clauses.
- Consider using a strategy pattern for parsing different `agtype` structures.

#### Next Steps:
- Implement refactoring for the `parse()` function.
- Review and refactor other functions as needed.

6. **[CRITICAL] Reduce cognitive complexity in API handlers (`python:S3776`)**
- Scope: `backend/app/api/v1/query.py`, `csv_importer.py`, `graph_delete_node.py`, `query_stream.py`, `graph.py`.
- Verified in repo: request validation, DB checks, and response shaping are all inside single large handlers.
- Fix approach:
  - Extract route-level orchestration from business logic:
    - validation helper(s)
    - query/build helper(s)
    - error translation helper(s)
  - Keep route handlers thin and compositional.
- Verification:
  - Existing endpoint tests + add focused unit tests for extracted helpers.

### Cognitive Complexity in API Handlers (S3776)

#### Analysis:
The following functions in `backend/app/api/v1/query_stream.py` exhibit high cognitive complexity:

1. **`stream_query_results()`**:
   - Handles multiple cases for streaming query results.
   - Contains deeply nested conditionals and loops.
   - Complexity arises from handling query validation, result parsing, and chunked streaming.

#### Recommendations:
- Refactor large functions into smaller, reusable components.
- Use helper functions to handle repetitive tasks like query validation and result parsing.
- Simplify nested conditionals by using early returns or guard clauses.
- Consider using a generator or coroutine for modular streaming logic.

#### Next Steps:
- Implement refactoring for the `stream_query_results()` function.
- Review and refactor other functions in `query_stream.py` as needed.

7. **[CRITICAL] Reduce cognitive complexity in frontend components (`typescript:S3776`)**
- Scope: `frontend/src/components/QueryEditor.tsx`, `GraphView.tsx`, `ResultTab.tsx`, `frontend/src/services/api.ts`.
- Verified in repo: keyboard/event handling and graph rendering behavior are dense in single functions/effects.
- Fix approach:
  - Extract composables/hooks/helpers:
    - keyboard handlers in `QueryEditor`
    - D3 event wiring chunks in `GraphView`
    - request/response/error handling utility split in `api.ts`
  - Keep each function below complexity threshold.
- Verification:
  - Run frontend unit tests and smoke test graph interactions manually.

8. **[CRITICAL] Repeated literals (`S1192`) in backend/docs**
- Scope:
  - `backend/app/services/metadata.py`: repeated string literal (`"does not exist"`)
  - `docs/sample-graph-test_graph.sql`: repeated literals in sample graph setup.
- Verified in repo: repeated literals are visible.
- Fix approach:
  - Introduce module-level constants in Python.
  - For SQL sample, reduce repetition by comments/template sections or variables where supported by script style.
- Verification:
  - Ensure docs SQL still executes on target setup; run relevant metadata unit tests.

9. **[MAJOR][VULNERABILITY] Hard-coded credential pattern detections (`python:S2068`, `yaml:S2068`)**
- Scope: mostly test fixtures and `deployment/docker-compose.yml`.
- Verified in repo: `password`/`PASSWORD` markers are present.
- Fix approach:
  - For tests: centralize placeholder credentials in constants and use neutral names (`TEST_DB_PASSWORD`) to reduce false positives.
  - For compose: rely on env interpolation only and remove any literal secret-like defaults.
- Verification:
  - Run backend tests and compose config validation.

10. **[MINOR][SECURITY] Logging user-controlled data (`pythonsecurity:S5145`)**
- Scope: `backend/app/api/v1/connections.py` (at least two findings).
- Verified in repo: f-string logs include user-provided identifiers.
- Fix approach:
  - Use structured logging with sanitized fields.
  - Avoid direct interpolation of user input into message text.
- Verification:
  - Run tests for connection endpoints and inspect logs for expected sanitized output.

11. **[MAJOR+] Duplication cleanup candidates (non-new-code, but worthwhile)**
- Scope:
  - intra-file duplication in `backend/app/services/agtype.py`
  - intra-file duplication in `frontend/src/components/GraphView.tsx`
  - historical cross-file duplication between CSV import modules
- Verified in repo:
  - `agtype.py` duplication around late-file path extraction logic is plausible.
  - Sonar line references for `GraphView.tsx` and `import_csv.py` are stale vs current tree; still worth re-assessing after fresh Sonar scan.
- Fix approach:
  - Extract repeated blocks into private helpers.
  - Re-run Sonar after current branch analysis to get accurate line mappings before editing based on old offsets.
- Verification:
  - Re-run Sonar and confirm duplicated block count decreases.

## Execution Order Recommendation

1. Apply global FastAPI convention fixes (`S8410`, `S8409`, `S8414`) in one backend sweep.
2. Refactor critical complexity hotspots in backend service/router files.
3. Refactor critical frontend complexity hotspots.
4. Address credential/logging security findings.
5. Refresh Sonar analysis for this branch and then resolve remaining duplication/literal findings with accurate line mappings.

## Test and Verification Notes

- Backend:
  - `make test-backend`
- Frontend:
  - `make test-frontend`
- Optional focused checks:
  - OpenAPI schema generation and route smoke tests after route signature/decorator changes.
  - Re-run Sonar scan to confirm issue burn-down and refreshed duplication offsets.
