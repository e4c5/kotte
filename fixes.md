# PR #16 — Actionable review items

Roadmap for implementing feedback from [pull/16](https://github.com/e4c5/kotte/pull/16) review threads. Non-actionable threads (test design, already-fixed UI, quote parser) are addressed via PR replies and resolved on GitHub.

---

## 1. `query_stream.py` — Enforce `max_rows` before emitting chunks; fix control-flow vs error record

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068148601  
**Also:** https://github.com/e4c5/kotte/pull/16#discussion_r3068156215

**File & context:** `backend/app/api/v1/query_stream.py` — streaming loop (~lines 161–239)

**Finding:** `emitted_rows` is incremented after each chunk is yielded. The check `if not has_more or len(parsed_rows) < chunk_size: break` runs *before* `if emitted_rows >= max_rows`, so the stream can (a) emit more than `max_rows` rows when the cap falls mid-chunk, and (b) exit on “last chunk” without emitting the cap-reached error record when the cap was exceeded on that chunk.

**Original suggestion:** Yield `error_chunk` when the cap is reached and simplify loop structure; enforce budget before yielding.

**Verified plan:**

1. Before building/yielding each chunk in the `while True` branch, compute `remaining = max_rows - emitted_rows`. If `remaining <= 0`, emit the existing `error_chunk` JSON and `break` (without yielding another data chunk).
2. When building `result_rows` from `parsed_rows`, cap the slice to `remaining` rows so a single DB fetch cannot produce a chunk larger than the remaining budget.
3. Optionally adjust the SQL `LIMIT` for the next iteration to `min(chunk_size, remaining)` to reduce over-fetching (still keep correctness via row cap).
4. Reconcile ordering: only `break` for natural end-of-stream *after* applying cap logic, or structure as: yield truncated chunk → update `emitted_rows` → if `emitted_rows >= max_rows` yield error and break → elif end of stream break → else continue.

**Testing strategy:** Extend `backend/tests/test_query_stream.py` with mocks returning fixed row counts per call to assert: (1) total rows never exceed `max_rows` (mock `settings.query_max_result_rows` or patch), (2) when cap is hit mid-stream, an error line is emitted after the last allowed data chunk. Run `make test-backend`.

**Risks:** Clients that relied on receiving full `chunk_size` rows every line until the end will see smaller final chunks; document NDJSON contract if needed.

---

## 2. `query_stream.py` — LIMIT/SKIP branch buffers entire result

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068156214

**File & context:** `backend/app/api/v1/query_stream.py` — `if has_limit or has_skip:` (~lines 111–159)

**Finding:** One `execute_cypher` call loads all rows into `parsed_rows`, defeating streaming for large `LIMIT` windows.

**Verified plan:**

1. **Short term:** Document in API/docs that when the query already contains LIMIT/SKIP, the server materializes the full window (or add a warning in the stream metadata once per response).
2. **Longer term:** For queries with LIMIT only, rewrite or wrap execution to page internally (e.g. repeated subqueries with SKIP/LIMIT chunks) using the same connection semantics as the main loop, or reject oversized LIMIT with 400 + guidance.

**Testing strategy:** Add a test with a mock that asserts `execute_cypher` call count when implementing paging; performance tests optional.

**Risks:** Cypher rewriting is error-prone; prefer documented limitation until a safe parser-based injection exists.

---

## 3. `analyze_pr.py` — Fail fast on GraphQL pagination inconsistency

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068156208

**File & context:** `.agents/skills/respond-pr-review-comments/scripts/analyze_pr.py` — `fetch_review_threads` (~118–120) and `fetch_issue_comments` (~141–143)

**Finding:** If `hasNextPage` is true but `endCursor` is missing, the code silently stops pagination and may produce partial comment context.

**Verified plan:**

1. Replace `if not cursor: break` with `raise RuntimeError(...)` including operation context (`fetch_review_threads` vs `fetch_issue_comments`) and a short snapshot of `pageInfo`.
2. Optionally log at error level before raising for CI debugging.

**Testing strategy:** Unit test with a mocked `run_gh_graphql` return that sets `hasNextPage: true` and omits `endCursor`, expecting `RuntimeError`.

**Risks:** Stricter behavior may surface GitHub API quirks; message should be clear for operators.

---

## 4. `connection.py` — Parameterize `statement_timeout` setup

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068156217

**File & context:** `backend/app/core/database/connection.py` — `transaction()` (~383–385)

**Finding:** `SET LOCAL statement_timeout = ...` uses an f-string.

**Verified plan:**

1. Use `await cur.execute("SET LOCAL statement_timeout = %(ms)s", {"ms": str(effective_timeout * 1000)})` or PostgreSQL-supported parameterized form, **or** `SELECT set_config('statement_timeout', %(timeout)s, true)` with a typed value per project conventions.
2. Verify psycopg accepts the parameter type for `SET LOCAL` (may require string milliseconds).

**Testing strategy:** Run `make test-backend`; any existing transaction timeout tests.

**Risks:** Some `SET` variants have limited parameter support; fallback to `set_config` if needed.

---

## 5. `manager.py` — DRY `get_backend_pid`

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068148648

**File & context:** `backend/app/core/database/manager.py` — `get_backend_pid` (~36–46)

**Finding:** Duplicate cursor execute/fetch for pooled vs provided connection.

**Verified plan:**

1. Extract `_fetch_backend_pid(self, conn: psycopg.AsyncConnection) -> Optional[int]` that runs `_SQL_BACKEND_PID` and returns `first_value(result)`.
2. `get_backend_pid`: if `conn` provided, call helper with it; else `async with self.db_conn.connection() as pooled: return await self._fetch_backend_pid(pooled)`.

**Testing strategy:** Existing DB unit tests; run `make test-backend`.

**Risks:** None significant.

---

## 6. `manager.py` — `get_query_pid` and `pg_stat_activity` on same connection

**Comment URL:** https://github.com/e4c5/kotte/pull/16#discussion_r3068156219

**File & context:** `backend/app/core/database/manager.py` — `get_query_pid` (~77–114)

**Finding:** Running the `pg_stat_activity` lookup on the same backend session can make `query` reflect the monitor query, so `query_text` filtering may not match the application query.

**Verified plan:**

1. Keep `SELECT pg_backend_pid()` on the connection under test (or the pool checkout that runs the workload).
2. Open a **second** connection from the pool for `SELECT ... FROM pg_stat_activity WHERE pid = %(pid)s ...` so the monitored session’s `query` field is not the lookup statement itself.
3. Preserve parameterized SQL and existing `query_text` / `first_value` behavior.
4. Audit call sites of `get_query_pid` for connection lifecycle (no leaks).

**Testing strategy:** Mock two connections if unit-testing; integration test optional where AGE is available.

**Risks:** Slightly higher pool usage; race window between PID read and activity snapshot remains inherent to `pg_stat_activity`.

---

## Summary

| Area | Files |
|------|--------|
| Streaming caps & memory | `query_stream.py`, `test_query_stream.py` |
| Script robustness | `analyze_pr.py` |
| SQL parameterization | `connection.py` |
| PID / activity helpers | `manager.py` |

After implementing, re-run `make test-backend` and `make test-frontend`, and close the corresponding GitHub review threads.
