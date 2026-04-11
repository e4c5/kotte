# Engineering backlog (internal review)

This document captures findings from an internal review of the `avurudu` improvement branch. Items are ordered by **priority** (P0 first). Use it for planning; update this file as items ship.

**Tracking:** Use the checklist below for at-a-glance status. Toggle `- [ ]` → `- [x]` when an item is done, and keep the short **Status** line under each item in sync (date + what shipped).

---

## Progress checklist

### P0 — Correctness / data integrity

- [x] **P0.1** — `transaction()` shares one physical connection with `execute_*` / `execute_cypher` (optional `conn` keyword; transactional call sites updated)

### P1 — Concurrency / consistency

- [x] **P1.1** — Safe metadata cache invalidation (`invalidate_property_metadata_cache`; `delete` / `clear(prefix=...)` under lock)

### P2 — API honesty / product clarity

- [x] **P2.1** — Edge `property_statistics` via `get_numeric_property_statistics_for_label` (aggregates `get_property_statistics`; passes discovered `properties` from metadata endpoint)

### P3 — Robustness / parity

- [x] **P3.1** — `execute_scalar` timeout parity (`asyncio.wait_for` + `query_timeout`) — *done with P0.1 (2026-04-11)*
- [x] **P3.2** — `execute_command` rollback on timeout / errors — *done with P0.1 (2026-04-11)*
- [x] **P3.3** — Pool metrics task logs failures (first failure with traceback; every 10th consecutive failure)

### P4 — Frontend polish

- [x] **P4.1** — Graph export blob URL lifecycle (`useGraphExport`; defer PNG revoke)
- [x] **P4.2** — Vitest `run` + `make test-frontend` uses `timeout` (`npm run test:run`, default 180s)

### Follow-ups (optional, not blocking)

- [x] **F.1** — Integration test `test_failed_query_in_transaction_does_not_poison_pool` (`USE_REAL_TEST_DB=true`)

---

## P0 — Correctness / data integrity

### P0.1 `transaction()` must share one physical connection with `execute_*` / `execute_cypher`

**Problem:** `DatabaseConnection.transaction()` checks out connection A and opens `conn.transaction()`, but `execute_query`, `execute_scalar`, `execute_command`, and `execute_cypher` each call `connection()` again and use **other** pool connections. Call sites that use `async with db_conn.transaction():` (e.g. node delete, CSV import) do **not** get multi-step atomicity; one connection sits idle in `BEGIN` while work runs elsewhere.

**Acceptance criteria:**

- Either all statements intended to be atomic run on the **same** `AsyncConnection`, or the public `transaction()` API is removed/renamed so misuse is impossible.
- Pool usage: no long-held idle transaction while other connections perform the real work.
- Tests prove atomicity (e.g. failure mid-flow rolls back visible effects) where the product requires it.

**Primary references:** `backend/app/core/database/connection.py`, `backend/app/core/database/cypher.py`, `backend/app/api/v1/graph_delete_node.py`, `backend/app/api/v1/csv_importer.py`.

**Status:** **Done** (2026-04-11). Optional keyword argument `conn` is implemented on `execute_query`, `execute_command`, `execute_scalar`, and `execute_cypher`; node delete, CSV import (`csv_importer`), and the simple CSV import insert loop pass the transaction connection. Idle second-connection misuse is removed for those paths. `execute_scalar` now honors `settings.query_timeout` via `asyncio.wait_for`; `execute_command` rolls back on failure/timeout like `execute_query`. Optional follow-up: an integration test with `USE_REAL_TEST_DB=true` that asserts rollback when a multi-step transactional flow fails mid-way.

---

## P1 — Concurrency / consistency

### P1.1 Safe metadata cache invalidation

**Problem:** `LegacyPropertyCache.invalidate` in `metadata.py` mutates `metadata_cache._cache` without acquiring `InMemoryCache`’s async lock, while normal paths use the lock.

**Acceptance criteria:**

- Invalidation goes through `InMemoryCache` APIs that hold the lock (e.g. `clear(prefix=...)`, `delete`, or new helpers), or invalidation is documented as test-only and removed from production paths.
- No silent `except Exception: pass` that hides invalidation failures without logging.

**Primary references:** `backend/app/services/metadata.py`, `backend/app/services/cache.py`.

**Status:** **Done** (2026-04-11). Replaced `LegacyPropertyCache` with async `invalidate_property_metadata_cache()`, which uses `metadata_cache.delete` and `metadata_cache.clear(prefix=...)`. Graph-wide invalidation also clears `counts:` and `stats:` prefixes for that graph. CSV import routes and `MetadataService` call sites use `await`. Tests in `TestInvalidatePropertyMetadataCache`.

---

## P2 — API honesty / product clarity

### P2.1 `get_numeric_property_statistics_for_label` is a stub

**Problem:** The method returns `{}`; `get_graph_metadata` still uses it for edge labels and builds `property_statistics`, so clients always see empty statistics for edges.

**Acceptance criteria (pick one):**

- Implement aggregation using existing per-property stats, **or**
- Stop populating / omit the field for edges until implemented, **or**
- Document in OpenAPI/model descriptions that edge numeric statistics are not yet available.

**Primary references:** `backend/app/services/metadata.py`, `backend/app/api/v1/graph.py`, `backend/tests/test_metadata.py`.

**Status:** **Done** (2026-04-11). `get_numeric_property_statistics_for_label` aggregates `get_property_statistics` per edge property with `asyncio.gather`; `get_graph_metadata` passes the already-discovered `properties` list to avoid a second discovery. `EdgeLabel.property_statistics` field description updated in `models/graph.py`.

---

## P3 — Robustness / parity

### P3.1 `execute_scalar` timeout parity

**Problem:** `execute_query` / `execute_command` use `asyncio.wait_for` around `execute`; `execute_scalar` does not.

**Acceptance criteria:** Same timeout semantics as other entry points (respect `settings.query_timeout` unless overridden).

**Primary reference:** `backend/app/core/database/connection.py`.

**Status:** **Done** (2026-04-11), same change set as P0.1 — `execute_scalar` uses `asyncio.wait_for` for `cur.execute`.

### P3.2 `execute_command` behavior on timeout

**Problem:** On `asyncio.TimeoutError`, `execute_query` rolls back; `execute_command` does not explicitly roll back.

**Acceptance criteria:** Documented, consistent behavior with the pool (rollback or explicit reset) and aligned with psycopg 3 expectations.

**Primary reference:** `backend/app/core/database/connection.py`.

**Status:** **Done** (2026-04-11), same change set as P0.1 — `_execute_command_on_conn` rolls back on timeout and on generic `Exception`.

### P3.3 Pool metrics background task

**Problem:** `_report_pool_metrics` swallows all exceptions silently.

**Acceptance criteria:** Log at debug/warning or increment a metric on repeated failure; avoid bare silence.

**Primary reference:** `backend/app/core/database/connection.py`.

**Status:** **Done** (2026-04-11). First failure logs `warning` with `exc_info=True`; every 10th consecutive failure logs again with counts. Successful runs reset the counter. `asyncio.CancelledError` is re-raised so task cancellation still works.

---

## P4 — Frontend polish

### P4.1 Graph export blob URL lifecycle

**Problem:** `useGraphExport` revokes object URLs immediately after triggering download; can be flaky in some browsers.

**Acceptance criteria:** Revoke after a microtask or timeout, or only revoke the SVG URL immediately; verify download still works.

**Primary reference:** `frontend/src/hooks/useGraphExport.ts`.

**Status:** **Done** (2026-04-11). SVG object URL revoked after click; PNG object URL revoked in a microtask so the browser can attach the download first.

### P4.2 Vitest non-watch CI

**Problem:** `make test-frontend` may leave Vitest in watch mode.

**Acceptance criteria:** CI/scripts use `vitest run` (or equivalent) for a clean exit.

**Primary reference:** `frontend/package.json`, `Makefile`.

**Status:** **Done** (2026-04-11). `npm run test:run` maps to `vitest run`. `make test-frontend` runs `timeout $(TEST_TIMEOUT) npm run test:run` (default **180s**) so hung workers or accidental watch mode cannot block forever. Use `TEST_TIMEOUT=600s make test-frontend` to extend. Interactive watch remains `npm test` (`vitest`).

---

## How to use this backlog

1. **Checklist first** — Update the [Progress checklist](#progress-checklist) when you start or finish work so the table of contents reflects reality.
2. **Ship P0 before** relying on transactional guarantees for delete/import flows in production (P0.1 is done).
3. **P1.1** (cache invalidation) is done; safe to increase concurrency against the metadata cache.
4. **P4.1–P4.2** and optional **F.1** are done.

When an item is done, add a **Status** line under its section (date + short summary) and check the box above.

---

## F.1 — Optional real-DB transaction test

**Goal:** After a failing `execute_query(..., conn=conn)` inside `transaction()`, the pool must still return a healthy connection.

**Status:** **Done** (2026-04-11). `tests/integration/test_transaction_rollback_real_db.py::test_failed_query_in_transaction_does_not_poison_pool` — skipped unless `USE_REAL_TEST_DB=true`; requires PostgreSQL with Apache AGE (same as app `connect`).
