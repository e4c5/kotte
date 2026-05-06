# Heavy Lift Items Plan — PR #48

This document captures the PR review comments tagged as **Heavy lift** that require non-trivial design or architectural changes. Each item describes the issue, the risk it poses, and a recommended implementation path.

---

## 1. PoolRegistry: Shared pool reuse bypasses credential/TLS validation

**File:** `backend/app/core/database/pool_registry.py:37-49`  
**Severity:** 🔴 Critical  
**Status:** Unresolved

### Issue
`PoolKey` is defined as `tuple[str, int, str, str]` — only `(host, port, database, user)`. `password` and `sslmode` are accepted in `get_or_create(...)` but deliberately excluded from the key. This means:

- A second session that connects to the same host/port/database/user but with a *different password* will silently reuse the existing pool, bypassing re-authentication.
- A session that requires a different `sslmode` (e.g. `require` vs `disable`) will also reuse the same pool, which can silently downgrade security or cause TLS handshake errors later.

### Solution
1. Expand `PoolKey` to include `password` and `sslmode`:
   ```python
   PoolKey = tuple[str, int, str, str, str, Optional[str]]
   # (host, port, database, user, password, sslmode)
   ```
2. Update `_make_key` to accept and return the new shape.
3. Update all call sites of `_make_key`, `touch()`, and `cleanup_idle()` to propagate the new key.
4. Add a regression test that creates two pools with identical host/db/user but different passwords and asserts they are distinct objects.

**Effort estimate:** Small refactor (~20 lines + tests). The change is mechanical but touches every caller of `_make_key` and `touch`.

---

## 2. PoolRegistry: `cleanup_idle()` race condition disconnects freshly reused pools

**File:** `backend/app/core/database/pool_registry.py:91-110`  
**Severity:** 🟠 Major  
**Status:** Unresolved

### Issue
`get_or_create()` updates `_last_used[key]` on the fast path (line 67) **outside** `_lock`, and `touch()` does the same (line 127). `cleanup_idle()` snapshots `idle_keys` inside `_lock` (line 95-98), then `await`s `pool.disconnect()` while still holding the lock (line 105).

This creates a TOCTOU race:
1. `cleanup_idle()` acquires the lock, computes `idle_keys`, and starts iterating.
2. While `cleanup_idle()` is `await`ing `disconnect()` for one pool, another request enters `get_or_create()` on the fast path (outside the lock), sees the pool is alive, updates `_last_used`, and returns it.
3. `cleanup_idle()` then `pop`s that pool and disconnects it, even though a caller is actively using it.

### Solution
Restructure `cleanup_idle()` so the eviction decision is atomic with respect to fast-path usage:

1. **Option A — lock-free timestamps:**
   - Add a `last_activity` atomic counter (or `asyncio.Lock` per pool) so `cleanup_idle()` can skip pools whose `_last_used` changed after the snapshot.
   - After each `disconnect`, re-check `_last_used[key]`; if newer than the snapshot threshold, abort the eviction for that key.

2. **Option B — snapshot-and-reconcile:**
   - Move the `idle_keys` snapshot **outside** the lock (just read the dict).
   - Then acquire the lock and re-verify each candidate is still idle before popping and disconnecting.
   - Keep `disconnect()` inside the lock to prevent the race entirely. This serializes pool creation and cleanup but is safe.

**Recommended:** Option B for simplicity. Change `cleanup_idle()` to:
```python
now = datetime.now(timezone.utc)
candidates = [
    k for k, last in self._last_used.items()
    if (now - last).total_seconds() > max_idle_seconds
]
async with self._lock:
    for key in candidates:
        if key not in self._last_used:
            continue
        if (now - self._last_used[key]).total_seconds() <= max_idle_seconds:
            continue
        pool = self._pools.pop(key, None)
        self._last_used.pop(key, None)
        if pool:
            try:
                await pool.disconnect()
            except Exception as exc:
                logger.warning(...)
```

**Effort estimate:** Small (~10 lines + race-condition regression test using `asyncio.gather`).

---

## 3. QueryTracker: Redis metadata TTL expires before long-running queries finish

**File:** `backend/app/services/query_tracker.py:140-166`  
**Severity:** 🟠 Major  
**Status:** Resolved (out of scope for this PR)

### Issue
`register_query()` writes metadata to Redis with a fixed TTL (`ex=self._ttl`, default 300s). `set_backend_pid()` refreshes the TTL once. However, if a query runs longer than `_ttl`, the Redis key disappears while `db_conn` is still live in local memory.

Consequences:
- `cancel_query()` from another worker instance returns "not found" even though the query is actively running.
- Cross-instance query visibility breaks for long-running analytics or bulk imports.

### Solution
Implement a **background heartbeat** that refreshes the Redis TTL while the query is active:

1. In `register_query()`, after writing the Redis key, spawn an `asyncio.Task` that loops every `ttl/2` seconds and calls `await self._client.expire(self._key(request_id), self._ttl)`.
2. Store the task handle in `self._heartbeat_tasks[request_id]`.
3. In `unregister_query()` and `cancel_query()`, cancel the heartbeat task.
4. On application shutdown, cancel all remaining heartbeat tasks.

**Alternative (lighter):** Refresh the TTL inline inside the query execution/streaming loop every N rows. This avoids background tasks but couples TTL management to the execution path.

**Effort estimate:** Medium (~30 lines + integration test for multi-minute queries).

---

## 4. GraphCanvas: Canvas mode lacks keyboard and screen-reader accessibility

**File:** `frontend/src/components/GraphCanvas.tsx:553-680`  
**Severity:** 🟠 Major  
**Status:** Resolved (out of scope for this PR)

### Issue
`GraphCanvas` renders nodes/edges to a `<canvas>` with pointer-only interaction. The SVG fallback (`GraphView`) provides focusable elements (`role="button"`, `tabindex`, Enter/Space handlers). When results exceed the canvas threshold, keyboard and screen-reader users lose the ability to activate or inspect graph elements.

### Solution
Add an **accessible overlay** that mirrors the canvas graph:

1. Render an invisible or visually-hidden SVG layer on top of the canvas containing `<rect>` or `<circle>` elements for each node and edge.
2. Give each element `role="button"`, `tabindex="0"`, and descriptive `aria-label` (e.g. `aria-label="Node: Person (name: Alice)"`).
3. Wire keyboard handlers (Enter, Space, Escape) to invoke the same callbacks used by the canvas (`onNodeClickRef`, `onNodeRightClickRef`, `clearLassoNodes`, etc.).
4. Keep the overlay positions synchronized with `transformRef` and `nodesArr` inside the animation loop or via a `useEffect` with `requestAnimationFrame`.
5. Respect `prefers-reduced-motion` by disabling the zoom animation for focus transitions.

**Effort estimate:** Large (~80-120 lines across GraphCanvas + new hook for overlay sync). Requires manual accessibility testing.

---

## 5. Auth: In-memory session objects leak `db_connection` on Redis TTL expiry

**File:** `backend/app/core/auth.py:35-46`  
**Severity:** 🟠 Major  
**Status:** Resolved (out of scope for this PR)

### Issue
`_local_session_objects` stores full session dicts (including `db_connection` objects) in process-local memory. When the corresponding Redis key TTL expires, the local dict is never cleaned up. Over time this leaks database connections and memory.

### Solution
Options ranked by complexity:

1. **Redis Keyspace Notifications** (best):
   - Enable `notify-keyspace-events Ex` in Redis.
   - Subscribe to `__keyevent@0__:expired` for session keys.
   - On expiry event, purge the matching entry from `_local_session_objects`.
   - Requires Redis config change and a background subscriber task.

2. **Lazy sweep on access** (simplest, already partially done):
   - `_async_get()` already detects expired sessions and evicts them.
   - The leak only affects sessions that *never* get accessed again after expiry.
   - Add a periodic background sweeper (every 5 minutes) that iterates `_local_session_objects`, checks Redis `exists`, and evicts dead entries.

3. **WeakValueDictionary**:
   - Store only weak references to the `db_connection` so it can be GC'd when the session consumer drops it.
   - Not ideal because the session metadata itself should also be purged.

**Recommended:** Option 2 for immediate relief, with Option 1 as a follow-up infrastructure task.

**Effort estimate:** Small for Option 2 (~15 lines + background task registration); Medium for Option 1 (requires deployment/Redis config changes).

---

## 6. Auth: Idle session cleanup lacks a background sweeper

**File:** `backend/app/core/auth.py:190-230`  
**Severity:** 🟠 Major  
**Status:** Resolved (out of scope for this PR)

### Issue
`_async_get()` checks idle timeout synchronously when a session is accessed, but there is no background process to proactively remove idle sessions from Redis or `_local_session_objects`. Idle sessions can linger indefinitely if never touched again.

### Solution
Reuse the sweeper from item 5 (or implement a dedicated one):

1. In `RedisSessionManager.__init__`, spawn a background `asyncio.Task` that sleeps for `session_idle_timeout / 2` and then calls a `_sweep_expired()` method.
2. `_sweep_expired()` iterates Redis keys matching `session:*`, checks `last_activity`, and deletes stale ones.
3. For `_local_session_objects`, the same sweeper checks Redis `exists` and purges local entries whose Redis key is gone.
4. Cancel the sweeper task on app shutdown.

**Effort estimate:** Small (~25 lines + shutdown hook). Can share infrastructure with item 5.

---

## 7. main.py: Shutdown cleanup is not failure-isolated

**File:** `backend/app/main.py:35-42`  
**Severity:** 🟠 Major  
**Status:** Unresolved

### Issue
The lifespan shutdown path runs `await audit.close()`, `await _us.close()`, and `await pool_registry.close_all()` sequentially without exception isolation. If `audit.close()` raises, the user-service pool and the shared graph connection pools are never closed, causing leaked DB connections on every restart.

### Solution
Wrap each cleanup step in its own `try/except` block so a failure in one does not abort the others:

```python
async def lifespan(app: FastAPI):
    # ... startup ...
    yield
    # Shutdown — each close is isolated
    try:
        await audit.close()
    except Exception as exc:
        logger.warning("Shutdown: audit.close() failed: %s", exc)
    try:
        await _us.close()
    except Exception as exc:
        logger.warning("Shutdown: user_service.close() failed: %s", exc)
    try:
        await pool_registry.close_all()
    except Exception as exc:
        logger.warning("Shutdown: pool_registry.close_all() failed: %s", exc)
```

**Effort estimate:** Small (~6 lines + lifespan integration test).

---

## 8. audit.py: Permanent circuit breaker and blocking on DB down

**File:** `backend/app/services/audit.py:41-70`  
**Severity:** 🔴 Critical / 🟠 Major  
**Status:** Unresolved

### Issue
`_get_pool()` has two related problems:

1. **Permanent circuit breaker:** `_pool_unavailable` is set to `True` on any connection failure and never reset automatically. Once the DB recovers, audit logging remains silently disabled until the process restarts.
2. **Blocking on DB down:** When `_pool_unavailable` is `False` and the DB is unreachable, every call blocks for 3 seconds (`timeout=3` on `p.open()`) before failing. Since `fire_and_forget()` is called on the critical path (login, logout, CSRF failures), this can serially delay many requests.

### Solution
1. Make the circuit breaker **retryable** with a time-based backoff:
   - Replace `_pool_unavailable` with `_pool_retry_after: Optional[datetime]`.
   - On failure, set `_pool_retry_after = now + timedelta(seconds=60)`.
   - On entry, skip the pool attempt if `now < _pool_retry_after`.
   - Provide a `reset_pool()` function (already exists) that clears the latch on health checks.

2. **Short-circuit faster:** Lower the `open()` timeout or add a pre-flight `asyncio.wait_for` around the whole `_get_pool()` body so audit failures are bounded to ~1 second instead of 3.

3. **Alternative (preferred for resilience):** Make `fire_and_forget()` truly non-blocking by pushing audit events to an in-memory queue and having a single background worker drain it. The worker can retry independently without blocking request handlers.

**Effort estimate:** Medium (~40 lines for retryable breaker + queue option; ~15 lines for simple timeout fix).

---

## Summary Table

| # | File | Issue | Effort | Priority |
|---|------|-------|--------|----------|
| 1 | `pool_registry.py` | PoolKey omits password/sslmode | Small | 🔴 Critical |
| 2 | `pool_registry.py` | `cleanup_idle()` race condition | Small | 🟠 Major |
| 3 | `query_tracker.py` | Redis TTL expires mid-query | Medium | 🟠 Major |
| 4 | `GraphCanvas.tsx` | Canvas mode not accessible | Large | 🟠 Major |
| 5 | `auth.py` | Local session object leak on expiry | Small–Medium | 🟠 Major |
| 6 | `auth.py` | No background idle session sweeper | Small | 🟠 Major |
| 7 | `main.py` | Shutdown cleanup not failure-isolated | Small | 🟠 Major |
| 8 | `audit.py` | Permanent circuit breaker + blocking on DB down | Medium | 🔴 Critical |

**Immediate action recommended:** Items 1, 2, and 8 (pool safety + audit resilience) should be addressed before the next release because they affect data isolation, stability, and observability. Items 3–7 can be scheduled as follow-up sprints.
