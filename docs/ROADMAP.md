# Kotte — Implementation Roadmap

_Created: 2026-04-18. Companion to `docs/REVIEW.md` (the holistic review)._

This is a **concrete, ticketed plan** derived from `REVIEW.md`. Every Milestone A ticket has the file, the location, the change shape, an acceptance check, and an estimate. Milestones B–D are sketched at the next-action level — drill into any of them when you're ready to start.

Tickets within a milestone are independently mergeable unless marked _depends on_.

---

## Table of contents

- [Milestone A — Stop the bleeding](#milestone-a--stop-the-bleeding)
- [Milestone B — CI and production deployment are real](#milestone-b--ci-and-production-deployment-are-real)
- [Milestone C — Make it a graph product](#milestone-c--make-it-a-graph-product)
- [Milestone D — Multi-user, multi-tenant, observable](#milestone-d--multi-user-multi-tenant-observable)
- [Suggested execution order](#suggested-execution-order)
- [Progress checklist](#progress-checklist)

---

## Milestone A — Stop the bleeding

Cheap, high-value fixes that close the gap between _what's wired_ and _what users see_. **Total: ~2 dev-days for one engineer.**

### A1. Wire the Settings modal (gear button + theme)

**Why:** `SettingsModal` exists and is importable but is never rendered open. `theme`, `defaultViewMode`, `queryHistoryLimit`, `autoExecuteQuery`, viz limits, table page size, default layout, and export format depend on it being reachable.

**Files & changes:**

- `frontend/src/pages/WorkspacePage.tsx`
  - Header (around line 333): add a gear `<button>` next to the Disconnect button that calls `setShowSettings(true)`. Use `aria-label="Open settings"`.
  - Around line 309: replace the hard-coded `bg-zinc-950 text-zinc-100` shell with classes derived from `useSettingsStore().theme` (`'dark' | 'light' | 'system'`). For `'system'`, key off `window.matchMedia('(prefers-color-scheme: dark)')`.
- `frontend/src/components/Layout.tsx` (lines 13–14): same theme-aware shell so non-workspace routes match.
- `frontend/tailwind.config.js`: enable `darkMode: 'class'` (currently implicit) and switch the workspace shell to `dark:bg-zinc-950 bg-white` style classes. Add a small `useTheme()` hook in `frontend/src/utils/` that toggles `document.documentElement.classList`.

**Acceptance:** Clicking gear opens `SettingsModal`. Toggling theme to `light` recolors the workspace background and text without reload.

**Estimate:** half a day.

---

### A2. Fix tab pin/unpin

**Why:** `WorkspacePage.tsx:329` passes `onTabUnpin={unpinTab}`, but `TabBar.Props` (`TabBar.tsx:3-10`) doesn't accept it; the pin button always calls `onTabPin`.

**Files & changes:**

- `frontend/src/components/TabBar.tsx`
  - Add `onTabUnpin?: (tabId: string, e: React.MouseEvent) => void` to `TabBarProps`.
  - Add it to the destructure (lines 12–19).
  - In the pin button onClick (lines 84–87), branch:

    ```ts
    onClick={(e) => {
      e.stopPropagation()
      if (tab.pinned) onTabUnpin?.(tab.id, e)
      else onTabPin?.(tab.id, e)
    }}
    ```

- `frontend/src/components/__tests__/TabBar.test.tsx`: add a test that clicks the pin button on a pinned tab and asserts `onTabUnpin` is called (the existing test already passes the prop).

**Acceptance:** Clicking the pin icon on a pinned tab unpins it. Existing tests pass.

**Estimate:** 30 min.

---

### A3. Add Pin / Hide actions in NodeContextMenu

**Why:** `togglePinNode` and `toggleHideNode` exist in `graphStore` but are unreachable from the UI.

**Files & changes:**

- `frontend/src/components/NodeContextMenu.tsx`
  - Extend props with `onPin?(nodeId)`, `onHide?(nodeId)`, plus boolean `isPinned`, `isHidden` to label the action correctly ("Pin" vs "Unpin", "Hide" vs "Show").
  - Add two new menu buttons between Expand and Delete (lines ~134, ~135). Match existing style.
- `frontend/src/components/ResultTab.tsx` (the file that mounts `NodeContextMenu`): pass new handlers wired to `useGraphStore.togglePinNode` / `toggleHideNode`. Read `isPinned`/`isHidden` from the same store.
- `frontend/src/components/GraphView.tsx`: confirm pinned nodes draw a small visual indicator (e.g. ring stroke). It already uses `pinnedNodes` for force pinning (lines 299–304); just add CSS `stroke-width` change when `pinnedNodes.has(d.id)`.

**Acceptance:** Right-click a node → Pin → node stays put under force. Right-click → Hide → node and its edges disappear from view. Both reverse via the same menu.

**Estimate:** 2–3 hours.

---

### A4. Remove the debug marker (or gate it on env)

**Why:** Production users see `GraphView marker: 2026-02-23-v3 | prop:1024x768 | view:...` permanently. Search `GraphView.tsx` for `GraphView marker:` to find the JSX (currently around line 358; line numbers will keep drifting, the marker string is the stable anchor).

**Files & changes:**

- `frontend/src/components/GraphView.tsx`, the `<text>` node containing `GraphView marker:` — replace with

  ```tsx
  {import.meta.env.DEV && (
    <div className="absolute left-2 top-2 ...">GraphView debug: ...</div>
  )}
  ```

**Acceptance:** `npm run build` + serve → no banner. `npm run dev` → banner still visible.

**Estimate:** 5 min.

---

### A5. Enforce viz limits in WorkspacePage before rendering

**Why:** `settingsStore.maxNodesForGraph/maxEdgesForGraph` (5000/10000) are never checked client-side. A 50k-node accidental query freezes the browser.

**Files & changes:**

- `frontend/src/pages/WorkspacePage.tsx`
  - Read `maxNodesForGraph`, `maxEdgesForGraph` from `useSettingsStore()` (line 47).
  - Before passing `tab` to `ResultTab` (line 367), compute

    ```ts
    const nodeCount = tab.result?.graph_elements?.nodes?.length ?? 0
    const edgeCount = tab.result?.graph_elements?.edges?.length ?? 0
    const overLimit = nodeCount > maxNodesForGraph || edgeCount > maxEdgesForGraph
    ```

  - If `overLimit` and `tab.viewMode === 'graph'`, force `viewMode='table'` and inject a banner above `ResultTab` explaining the limit and linking to settings.

**Acceptance:** Run a query returning 6000 nodes with default limits → table view auto-selected, banner visible, performance unaffected.

**Estimate:** 1–2 hours.

---

### A6. Unify the label color palette

**Why:** `nodeColors.ts:LABEL_COLORS` is a fixed array indexed in **insertion order**, while `graphStyles.ts` uses `d3.scaleOrdinal(d3.schemeCategory10)` with **its own** insertion map. Same labels can get different colors in pill vs node depending on which is rendered first.

**Files & changes:**

- `frontend/src/utils/nodeColors.ts`: export `LABEL_COLORS` and the `getNodeLabelColor` map.
- `frontend/src/utils/graphStyles.ts`
  - Replace `const colorScale = d3.scaleOrdinal(d3.schemeCategory10)` with `import { getNodeLabelColor } from './nodeColors'` and have `getDefaultNodeColor` delegate.
- Add a unit test in `frontend/src/utils/nodeColors.test.ts` that asserts the same label resolves to the same color when called via both code paths.

**Acceptance:** Sidebar pill color for label `Person` matches the node circle color in the graph.

**Estimate:** 1 hour.

---

### A7. Fix `expand_node` for `depth != 1` ✅ shipped

**Status:** Merged to `main` via PR #27 on 2026-04-18 (see commit on `fix/expand-node-depth`). Re-reading the on-disk Cypher revealed the original review wording was slightly off: the live query was already `RETURN DISTINCT m, rel` (no scope error), but the real depth-bug it was masking was that **intermediate nodes were silently dropped** for `depth > 1` — a depth-2 expansion returned the endpoint plus both relationships, but never the middle hop, so the frontend rendered floating edges with no node at one end.

**What shipped (`backend/app/api/v1/graph.py:330–352`):**

```cypher
MATCH path = (n)-[*1..{depth}]-(m)
WHERE id(n) = $node_id
WITH n, path
LIMIT $limit
UNWIND nodes(path) as pn
UNWIND relationships(path) as rel
RETURN DISTINCT n, pn, rel
```

Notes:

- `nodes(path)` (not just `m`) restores intermediate hops; the existing Python parser (`api/v1/graph.py:362-389`) already dedupes nodes by id and edges by id, so the per-path Cartesian explosion is bounded and harmless.
- `LIMIT` is applied to whole paths *before* `UNWIND`, so dense neighbourhoods can't blow up the response. With `limit=100` and `depth=2`, the worst case is ~600 rows over the wire; in practice far fewer after path overlap.
- `n` is now also returned so the response is self-describing — the frontend doesn't have to assume the source node is "obviously" the one the user clicked.
- The redundant `DISTINCT path` from the old version is gone; paths in a `MATCH` are already unique tuples.

**Tests (`backend/tests/integration/test_graph.py:257–319`):** new `test_expand_node_depth_two_returns_intermediate_nodes` simulates a 2-hop AGE response with three nodes (clicked, intermediate, endpoint) and two relationships, and asserts (a) all three nodes come back deduped, (b) both edges come back, and (c) the Cypher actually sent to `execute_cypher` contains `[*1..2]`, `nodes(path)`, `relationships(path)`, and `WITH n, path`, with `params={node_id: 1, limit: 100}`.

Full backend suite: 228 passed, 8 skipped, 2 unrelated `test_query_stream` failures that pre-date this branch and are tracked separately.

---

### A8. Make the per-user rate limit actually fire

**Why:** `RateLimitMiddleware` reads `request.scope["session"]["user_id"]` (`middleware.py:243`). The signed cookie session set at login stores `session_id`, not `user_id`. Looking at `auth.py:50-72`, the `SessionManager` knows the user_id but it isn't reflected into the Starlette session.

**Pick one of two fixes (recommend B):**

- **A.** In `backend/app/api/v1/auth.py` login handler, after `request.session["session_id"] = sid`, also `request.session["user_id"] = user.id`.
- **B.** In `backend/app/core/middleware.py:243`, replace

  ```python
  user_id = request.scope.get("session", {}).get("user_id") if "session" in request.scope else None
  ```

  with

  ```python
  sess_id = request.scope.get("session", {}).get("session_id")
  user_id = session_manager.get_user_id(sess_id) if sess_id else None
  ```

  This avoids drift between the cookie and `SessionManager`. Add `from app.core.auth import session_manager` at top.

**Test:** add a regression test in `backend/tests/test_middleware.py` that mocks the request, sets `scope["session"]["session_id"]`, registers a session in `session_manager`, fires `rate_limit_per_user + 1` calls, and asserts the final one raises 429.

**Acceptance:** Per-user 429 is reachable; `rate_limit_per_minute_per_user` becomes a real knob.

**Estimate:** 1–2 hours.

---

### A9. Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example`

**Why:** Repo hygiene; QUICKSTART references `cp .env.example`.

**Files:**

- `LICENSE`: pick a license (Apache AGE is Apache-2.0; Apache-2.0 or MIT are both fine for Kotte). Add the standard text and copyright line.
- `CHANGELOG.md`: seed with `## [0.1.0] - 2026-04-18` and bullet the items shipped to date (the P0–P4 backlog work that predates this roadmap, plus the Milestone A items as you ship them).
- `backend/.env.example`: enumerate every key from `backend/app/core/config.py:Settings` with a default and a one-line comment. Mark required-in-prod ones (`SESSION_SECRET_KEY`, `MASTER_ENCRYPTION_KEY`).

**Acceptance:** `cp backend/.env.example backend/.env` produces a working dev config; root `LICENSE` and `CHANGELOG.md` exist.

**Estimate:** 1 hour.

---

### A10. (Bonus, free) Surface JSON parameter parse errors instead of silently dropping them

**Why:** `QueryEditor.tsx:208-214` returns `{}` on bad JSON. Users get "no rows" with no indication why.

**Files & changes:**

- `frontend/src/components/QueryEditor.tsx`: change `getQueryParams` to return `{ ok: true, value }` or `{ ok: false, error }`. In the editor, render a small red caption under the params textarea on parse failure and disable Run.

**Acceptance:** Type `{bad json` → red error appears, Run button disabled.

**Estimate:** 1 hour.

---

### A11. Add additive double-click expand (with reversible "isolate" mode)

**Why:** Until very recently Kotte had no double-click affordance on a node at all. A first attempt to add one (on the now-discarded `double-click` branch) wiped the canvas in two phases on every double-click — first by filtering the existing `graph_elements` to the clicked node's incident edges, then by replacing the entire result with the API expansion. That code never landed on `main`. Every comparable tool (Neo4j Browser, Apache AGE Viewer, Memgraph Lab, Linkurious, Bloom) instead treats double-click as **additive expansion**: the clicked node's neighbours are merged into the existing canvas, preserving positions, pins, and prior expansions. The destructive "show only this node and its neighbours" behaviour belongs on an explicit menu action with an undo, not on the primary navigation gesture.

Why the additive design matters (and why the destructive attempt was rightly discarded):

- Wiping prior context (query result, earlier expansions, drag positions, pin state) on every double-click is intolerable in a graph explorer. There is no undo and re-running the original query won't restore positions.
- A two-phase rebuild creates a visible flicker (sparse → API result, ~50–500 ms apart).
- A celebrity node with 5,000 neighbours silently shows 100 random ones when the `limit` cap is not surfaced — and the user has no UI to pick a relationship type or direction.
- A `useRef` for camera focus that lives outside React's reactive flow makes the camera land in the wrong place on rebuilds.
- The right-click "Expand neighborhood" path already had the correct primitive — `mergeGraphElements` on `queryStore`. Double-click should reuse it, not duplicate it destructively.

The work splits cleanly into three PRs, sized to ship and merge independently.

#### Phase 1 — Additive double-click expand ✅ shipped

**Status:** Merged to `main` via PR #23 on 2026-04-19 (commits `461b202` test scaffold, `dc11d06` implementation).

- Added `frontend/src/utils/graphMerge.ts` — pure helper. Dedups nodes by `id` and edges by `(source, target, label)`. Tolerates edges whose endpoints have been mutated to `GraphNode` references by D3's force layout. Returns the ids of newly-added elements so callers can drive camera focus or pin animations later. 10 unit tests pin the contract.
- Refactored `queryStore.mergeGraphElements` to delegate to the pure helper and to return `{ addedNodeIds, addedEdgeIds }` instead of `void`. As a side effect, the right-click expand path no longer accumulates duplicate edges across repeated expansions of the same neighbourhood (the previous id-based dedup missed AGE-generated edge ids that change across expansions).
- Added `onNodeDoubleClick` prop to `GraphView`; the dblclick listener calls `preventDefault()` and `stopPropagation()` so `d3-zoom`'s default dblclick-to-zoom does not fire on top of the expand.
- Threaded `onNodeDoubleClick` through `ResultTab` to `WorkspacePage`, where `handleDoubleClickNode` delegates to the existing `handleExpandNode`.
- Acceptance check: double-clicking a node merges its first-hop neighbours; existing nodes keep positions; pinned nodes stay pinned; double-clicking the same node twice does not duplicate edges. Frontend tests: 34/34 passing. tsc error count dropped by 1 (a pre-existing `GraphEdge` type lie at the queryStore boundary is now resolved).

#### Phase 2 — Camera focus on newly-added neighbourhood

**Why:** Today the canvas just shifts whatever D3's simulation does after the merge. Users expect the view to centre on what they just expanded. The pure helper already returns the newly-added node ids; phase 2 consumes them.

**Files & changes:**

- `frontend/src/stores/graphStore.ts` — add `cameraFocusNodeId: string | null` and `cameraFocusAnchorIds: string[]` (the union of `{clicked node} ∪ addedNodeIds`), plus setters.
- `frontend/src/pages/WorkspacePage.tsx` — in `handleDoubleClickNode`, after the merge, call `setCameraFocusAnchorIds([nodeId, ...addedNodeIds])`. (Use the new return value from `mergeGraphElements`.)
- `frontend/src/components/GraphView.tsx` — read `cameraFocusAnchorIds` from the store; when it changes and is non-empty, animate the d3-zoom transform to fit those nodes in the viewport with a smooth `transition().duration(400)`. Briefly pin the anchor for ~2s (`fx`/`fy` set, then cleared on `setTimeout(2000)`) so the simulation settles around the focus.
- After the animation the page clears `cameraFocusAnchorIds` so subsequent simulation ticks don't keep retriggering it.

**Acceptance:** Double-clicking a node smoothly recentres the view on the union of the clicked node and its newly-added neighbours. The clicked node is briefly pinned then released. The animation does not re-fit on every simulation tick.

**Estimate:** 2–3 hours.

#### Phase 3 — Explicit reversible "isolate" mode

**Why:** The "show only this node and its neighbourhood" gesture is genuinely useful — but as an explicit, reversible action, not as an accident of double-clicking.

**Files & changes:**

- `frontend/src/components/NodeContextMenu.tsx` — add a new menu item `Show only this & its neighbourhood`, wired to a new `onIsolateNeighborhood` prop.
- `frontend/src/stores/queryStore.ts`
  - Add `previousGraphElements?: GraphElements | null` per tab.
  - Add `isolateNeighborhood(tabId, nodeId)`: snapshots `tab.result.graph_elements` into `previousGraphElements`, then rewrites `graph_elements` to keep only the node and its incident edges/endpoints **from the current canvas** (no API call — this is a deterministic client-side filter).
  - Add `restoreGraphElements(tabId)`: copies `previousGraphElements` back and clears the snapshot.
- `frontend/src/components/ResultTab.tsx`
  - Pass an `onIsolateNeighborhood` handler to `NodeContextMenu` that calls `isolateNeighborhood(activeTabId, nodeId)`.
  - When `tab.previousGraphElements` is set, render a `← Back to full result` breadcrumb above the graph; clicking it calls `restoreGraphElements(tab.id)`.

**Acceptance:** Right-click → `Show only this & its neighbourhood` collapses the canvas to the local neighbourhood; a `← Back to full result` breadcrumb appears; clicking it restores the previous canvas exactly. A unit test on `queryStore.isolateNeighborhood` + `restoreGraphElements` confirms the snapshot round-trips.

**Estimate:** 2–3 hours.

---

## Milestone B — CI and production deployment are real

Bigger but well-scoped. Listed as headline tickets here; expand into A-style detail when starting. **Total: ~2 weeks for one engineer.**

### B1. GitHub Actions: `backend-ci.yml`

- Jobs: `lint` (ruff + black + mypy), `unit` (pytest, no DB), `integration` (pytest with `services: postgres-age` container, `USE_REAL_TEST_DB=true`).
- Use `apache/age:PG16_latest` as service.
- Cache `~/.cache/pip` and `backend/venv`.

### B2. GitHub Actions: `frontend-ci.yml`

- `lint` (eslint), `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `build` (`vite build`).
- Cache `~/.npm` keyed by `package-lock.json`.

### B3. GitHub Actions: `container.yml`

- Build both images on tag pushes; push to GHCR.
- `trivy image` scan with severity `HIGH,CRITICAL` failing the build.

### B4. Multi-stage backend image

- `deployment/backend.Dockerfile`: stage 1 `python:3.11-slim` builder with build deps + `pip install --target=/app/site-packages`; stage 2 `python:3.11-slim` runtime, copy site-packages and source, `USER kotte`, `HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health`.

### B5. Multi-stage frontend image (production)

- New file `deployment/frontend.Dockerfile.prod`: stage 1 `node:20-alpine` runs `npm ci` + `npm run build`; stage 2 `nginx:alpine` with a custom `nginx.conf` doing SPA fallback + gzip + cache headers. Expose 80.
- Keep current `frontend.Dockerfile` for dev compose.

### B6. Compose split

- `deployment/docker-compose.dev.yml` (current behavior, source mounts).
- `deployment/docker-compose.prod.yml` (uses `Dockerfile.prod`, `ENVIRONMENT=production`, secrets via `--env-file`, `restart: unless-stopped`, no source mounts, `mem_limit`/`cpus` per service).

### B7. Migrations system

- Add `alembic` to `backend/requirements.txt`; init under `backend/alembic/`.
- First migration: schema-bootstrap that creates AGE extension, runs the index-creation logic from `backend/scripts/migrate_add_indices.py`, and adds a future `users` table stub.
- New Make target `migrate-up`.

### B8. Pre-commit

- `.pre-commit-config.yaml` with hooks: `ruff --fix`, `black`, `prettier` (frontend), `eslint`, `trailing-whitespace`, `check-yaml`, `cspell`.
- README note: `pre-commit install`.

### B9. Doc reconciliation pass (no code changes, just docs)

- `docs/CONFIGURATION.md`: drop unimplemented `sqlite`/`postgresql`/`redis` credential backends, or move them to a "Roadmap" section.
- `docs/QUICKSTART.md`: rewrite the "Next Steps" so it doesn't read like the visualizer is unbuilt.
- `docs/ARCHITECTURE.md`: change `app/core/security.py` references to `app/core/middleware.py`, `app/core/auth.py`, `app/core/credentials.py`.
- `docs/KUBERNETES_DEPLOYMENT.md`: add a banner "Status: planned, not shipped" until manifests land.

---

## Milestone C — Make it a graph product

What moves Kotte from "feature complete v0.1" to something a user would prefer over `psql` + Cytoscape. **Total: ~3–4 weeks for one engineer.**

### C1. CodeMirror 6 Cypher editor

- Add `@codemirror/state`, `@codemirror/view`, `@codemirror/language`, `@lezer/highlight`. Use `lang-cypher` (community grammar) or build a minimal Lezer grammar.
- Replace the `<textarea>` in `QueryEditor.tsx`. Wire history/run keybindings.
- Schema-aware autocomplete: feed it the labels & properties from `useGraphStore().metadata`. Hook into CodeMirror's `autocompletion()`.

### C2. Visualization upgrades

- Arrowheads via `<defs><marker>`; refer marker by edge color via `markerUnits="userSpaceOnUse"`.
- Curved edges and parallel-edge offsetting (compute index among edges sharing endpoints, draw quadratic Bézier with offset).
- Self-loop rendering (draw a small arc above the node).
- Add a Canvas/PixiJS renderer (`GraphCanvas.tsx`), mount it instead of `<svg>` when `nodes.length > 1500`. Keep the same `GraphViewProps` so callers don't change.
- Minimap component reading the same simulation positions (transformed by `d3-zoom`).
- Lasso multi-select using `d3-brush` with a modifier key.

### C3. Streaming end-to-end

- `ResultTab` decides between `executeQuery` and `streamQuery` based on a row threshold (e.g. `> 5000` rows expected, or always for `viewMode='table'`).
- `TableView` already accepts `streaming`/`onLoadMore`; wire them.
- `frontend/src/services/query.ts`: add `AbortSignal` to `stream()`. Hook to a Cancel button.
- Backend `query_stream.py:144-229`: replace the materialise-then-chunk path with a real `psycopg` server-side cursor (`async with conn.cursor(name='kotte_stream')`), iterating chunks of N.

### C4. Schema sidebar 2.0

- In `MetadataSidebar.tsx`, expand each label into a collapsible panel showing properties (already in the `GraphMetadata` type, just unrendered), property types from sampling, an "indexed" badge from `pg_indexes`, and "Sample 5 rows" + "Generate match query" actions.

### C5. Saved queries / templates UI

- `services/query_templates.py` already exposes templates; add a left-rail Library panel with categories. Click → fill editor with the template; render a parameter form from `param_schema`.

### C6. Read-only mode that's safe

- Replace the regex in `query.py:124-136` with either:
  - **Server-side enforcement**: open the cypher() call in a `BEGIN; SET TRANSACTION READ ONLY; ...` block, and let PG reject mutations. Catch the `read_only_sql_transaction` SQLSTATE (25006) and translate to `QUERY_VALIDATION_ERROR`.
  - **Or** integrate a Cypher parser library and walk the AST for write clauses.
- Add a `mutation_confirmed` boolean to the request schema for the explicit-mutation path; UI shows a confirmation modal listing affected labels before sending.

### C7. Expand options popover + truncation indicator

Builds on **A11**. Today expansion is hard-coded to "all relationship types, both directions, depth 1, limit 100, no feedback when truncated." That's fine as a default; users need finer control once they've explored a few hops.

- **Backend** — extend `NodeExpandRequest` (`backend/app/models/graph.py`):
  - `edge_labels: list[str] | None = None` — when set, restrict the expansion to those relationship types.
  - `direction: Literal['in', 'out', 'both'] = 'both'` — drive the Cypher arrow direction (`(n)-[r]->(m)` / `(n)<-[r]-(m)` / `(n)-[r]-(m)`).
  - Use validated label names (reuse `validate_label_name`) when interpolating into the relationship pattern.
- **Backend** — extend `NodeExpandResponse`:
  - `truncated: bool` — true when `len(nodes) >= request.limit`.
  - `total_neighbours: int` — a separate cheap `MATCH (n)-[r]-(m) WHERE id(n) = $node_id RETURN count(DISTINCT m)` so the UI can show "100 of 1,247".
- **Frontend** — replace the right-click "Expand neighbourhood" menu item with a small popover that shows: relationship-type checkboxes (populated from `useGraphStore().metadata.edge_labels`), an in/out/both toggle, depth selector (1 or 2), and a limit input (default 100, max 1000).
- **Frontend** — render a small badge on the cluster of newly added nodes after an expansion: `100 of 1,247 — refine to see more`. Clicking the badge re-opens the expand popover with the same node pre-selected.
- **Frontend (nice-to-have)** — when the metadata sidebar already knows a node's degree (from the meta-graph endpoint), draw a small numeric badge on each node showing how many neighbours are still hidden. Requires a small `count_hidden_neighbours` helper that diffs `total_neighbours` against currently-visible incident edges.

**Acceptance:** Right-click → expand popover lets the user pick edge type and direction. Hitting a 100-row cap renders a "100 of N" badge that re-opens the popover. The default depth-1 path still works unchanged when no options are passed.

---

## Milestone D — Multi-user, multi-tenant, observable

Only if you intend Kotte to be deployed beyond a single analyst. **Total: ~4–6 weeks; intentionally long because the multi-tenant pieces are interlocked.**

### D1. DB-backed users (Alembic migration adds `users`, `user_roles`)

- Replace `services/user.py` with a SQLAlchemy/asyncpg-backed implementation. Keep API.
- New routes `POST /api/v1/users` (admin only), `GET /me`, `PATCH /me/password`.
- Optional OIDC via `authlib`.

### D2. Redis-backed `SessionManager` and `query_tracker`

- Switch in-memory dicts to Redis with TTL = `session_max_age`.
- Cleanly call `DatabaseConnection.disconnect()` in a Redis keyspace-notification handler when a session expires (closes the per-session pool leak).

### D3. Shared connection pool per `(host, db, user)` tuple

- Replace per-session `AsyncConnectionPool` with a process-wide `PoolRegistry` keyed by `(host, db, user)`. Sessions hold a key, not a pool. Idle pools reaped after N minutes.

### D4. OpenTelemetry

- `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-psycopg`. Trace IDs flow into `request.state.request_id`.
- Add an OTLP exporter wired to env vars; document Tempo/Jaeger setup.

### D5. First-class audit log

- New table `audit_events` (Alembic). `services/audit.py` with `record(event, actor_id, request_id, payload)`. Replace `SECURITY:` log-prefix patterns at:
  - `middleware.py` (CSRF, rate limit)
  - `api/v1/auth.py` (login/logout)
  - `api/v1/query.py` (mutation execute)
  - `api/v1/connections.py` (saved-connection CRUD).

### D6. CSV importer hardening

- Stream-parse with the stdlib `csv` module (RFC-4180 quoting).
- Use parameterized `cypher()` calls (one per row, batched with `psycopg.AsyncCursor.executemany`) instead of embedded JSON literals.
- For files > N MB: COPY into a staging table `kotte_import_{job}`, then a single Cypher `LOAD/UNWIND` over the staging table.
- Add an idempotency key column; `ON CONFLICT DO NOTHING` on retries.

---

## Suggested execution order

1. **Week 1**: A1, A2, A3, A4, A6, A7, A11 phases 2–3 (UI quick wins + the AGE bug + finishing the additive double-click work). A11 phase 1 already shipped.
2. **Week 2**: A5, A8, A9, A10 + start B1/B2 (CI for tests/lint).
3. **Weeks 3–4**: B3–B6 (containers + compose split + first deployment dry-run).
4. **Weeks 5–6**: B7–B9 (migrations, pre-commit, doc reconciliation) + start C1 (CodeMirror).
5. **Weeks 7–10**: C1–C3 (editor + viz + streaming) — biggest UX visibility.
6. **Weeks 11–12**: C4–C6.
7. **Quarter 2**: D as needed, scoped by who's actually deploying multi-tenant.

---

## Progress checklist

Toggle `- [ ]` → `- [x]` as items ship, and add a short **Status** line under the ticket (date + what shipped + PR #) so the next reader can reconstruct what changed.

### Milestone A — Stop the bleeding

- [ ] **A1** — Wire the Settings modal (gear button + theme)
- [ ] **A2** — Fix tab pin/unpin
- [ ] **A3** — Add Pin / Hide actions in NodeContextMenu
- [ ] **A4** — Remove the debug marker (or gate it on env)
- [ ] **A5** — Enforce viz limits in WorkspacePage before rendering
- [ ] **A6** — Unify the label color palette
- [x] **A7** — Fix `expand_node` for `depth != 1` (PR #27 on `fix/expand-node-depth`; depth-2 now returns intermediate nodes via `nodes(path)`)
- [ ] **A8** — Make the per-user rate limit actually fire
- [ ] **A9** — Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example`
- [ ] **A10** — Surface JSON parameter parse errors instead of silently dropping them
- [~] **A11** — Add additive double-click expand (with reversible "isolate" mode)
  - [x] Phase 1 — additive double-click via shared `mergeGraphElements` (PR #23, commits `461b202`, `dc11d06` on `main`)
  - [ ] Phase 2 — camera focus animation on newly-added neighbourhood
  - [ ] Phase 3 — explicit reversible "isolate" context-menu action with `← Back to full result` breadcrumb

### Milestone B — CI and production deployment are real

- [ ] **B1** — GitHub Actions: `backend-ci.yml`
- [ ] **B2** — GitHub Actions: `frontend-ci.yml`
- [ ] **B3** — GitHub Actions: `container.yml`
- [ ] **B4** — Multi-stage backend image
- [ ] **B5** — Multi-stage frontend image (production)
- [ ] **B6** — Compose split (dev / prod)
- [ ] **B7** — Migrations system (Alembic)
- [ ] **B8** — Pre-commit
- [ ] **B9** — Doc reconciliation pass

### Milestone C — Make it a graph product

- [ ] **C1** — CodeMirror 6 Cypher editor
- [ ] **C2** — Visualization upgrades (arrows, curves, self-loops, canvas, minimap, lasso)
- [ ] **C3** — Streaming end-to-end
- [ ] **C4** — Schema sidebar 2.0
- [ ] **C5** — Saved queries / templates UI
- [ ] **C6** — Read-only mode that's safe
- [ ] **C7** — Expand options popover + truncation indicator (depends on **A11**)

### Milestone D — Multi-user, multi-tenant, observable

- [ ] **D1** — DB-backed users
- [ ] **D2** — Redis-backed `SessionManager` and `query_tracker`
- [ ] **D3** — Shared connection pool per `(host, db, user)` tuple
- [ ] **D4** — OpenTelemetry
- [ ] **D5** — First-class audit log
- [ ] **D6** — CSV importer hardening
