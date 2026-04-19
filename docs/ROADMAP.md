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

### A8. Make the per-user rate limit actually fire — ✅ shipped (PR #29, branch `fix/per-user-rate-limit`)

**Why (original):** `RateLimitMiddleware` read `request.scope["session"]["user_id"]`. The signed cookie session set at login stores `session_id`, not `user_id`. The `SessionManager` knew the `user_id` but never reflected it into the Starlette session, so the per-user branch was unreachable and `rate_limit_per_user` was dead config.

**Fix shipped (option B):** in `backend/app/core/middleware.py:241-257`, the lookup now resolves the user via `session_manager` instead of off the cookie:

```python
session_id = (
    request.scope.get("session", {}).get("session_id")
    if "session" in request.scope
    else None
)
user_id = None
if session_id:
    from app.core.auth import session_manager
    user_id = session_manager.get_user_id(session_id)
```

This means the cookie can never silently drift from `SessionManager` (option A would have required the login handler and the middleware to agree on what's in `request.session` forever). The `session_manager` import is lazy to mirror `CSRFMiddleware` and to keep `app.core.middleware` independent of `app.core.auth` at module-load time.

**Tests added (`backend/tests/test_middleware.py::TestRateLimitPerUser`):**

1. `test_per_user_rate_limit_raises_429_after_n_calls` — `rate_limit_per_user + 1` calls raise `APIException(429, RATE_LIMITED)` (driven by calling `dispatch` directly to bypass FastAPI's middleware-exception plumbing).
2. `test_per_user_buckets_are_independent` — user A hitting their cap doesn't throttle user B.
3. `test_unknown_session_id_does_not_enforce_per_user_quota` — stale/forgotten session IDs in the cookie don't cause all such traffic to be bucketed under one empty key.
4. `test_no_session_in_scope_does_not_enforce_per_user_quota` — anonymous traffic skips the per-user check entirely.

The fixture monkeypatches `settings` via `app.core.middleware`'s namespace (not via a fresh `from app.core.config import settings`) because the `test_app` conftest fixture reloads `app.core.config`, which would leave the middleware reading a stale `settings` instance.

**Acceptance:** Per-user 429 is reachable; `rate_limit_per_user` is a real knob. Verified by the 4 new tests; full suite at 235 passed / 8 skipped.

**Follow-up known but out of scope here:** when the per-IP or per-user cap fires, the resulting `APIException` is raised from a `BaseHTTPMiddleware`, where FastAPI's `add_exception_handler` doesn't intercept it. In production this currently lands as a 500 (with `INTERNAL_ERROR` logged) rather than a clean 429 JSON response, for both the IP and user paths. Tracking separately — likely fix is to have `RateLimitMiddleware` return a `JSONResponse(status_code=429)` directly instead of raising.

---

### A9. Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example` — ✅ shipped (PR #30, branch `chore/license-changelog-env`)

**Why:** Repo hygiene; QUICKSTART referenced `cp .env.example` but the file didn't exist; no LICENSE meant the repo wasn't legally reusable; commit cadence had reached the point where a CHANGELOG starts to pay off.

**Shipped:**

- **`LICENSE`** — verbatim Apache License 2.0 text from `https://www.apache.org/licenses/LICENSE-2.0.txt`. Apache-2.0 chosen to match Apache AGE itself and for the explicit patent grant; MIT and AGPLv3 were also under consideration but the user explicitly skipped the choice and Apache-2.0 was applied as the conservative default. Trivial to swap before the first tagged release if a different license is preferred.
- **`NOTICE`** — Apache-convention attribution file (`Copyright 2026 Raditha Dissanayake and the Kotte contributors`). Keeping `LICENSE` as the verbatim Apache text avoids the modify-the-license trap.
- **`CHANGELOG.md`** — Keep-a-Changelog 1.1.0 / SemVer format. Seeded with an `[Unreleased]` section (capturing this PR's additions) and a `[0.1.0] - 2026-04-19` entry that summarises the Milestone A work shipped so far (review docs, A11 phase 1, A2, A4, A7, A8) plus the test-stream cap-warning fixes from PR #28. Pre-roadmap commit history is intentionally not enumerated.
- **`backend/.env.example`** — enumerates every key on `app.core.config.Settings` plus `ADMIN_PASSWORD` (which lives in `services/user.py`, not `Settings`), grouped by concern with one-line comments and explicit `**REQUIRED IN PRODUCTION**` markers on `SESSION_SECRET_KEY`, `ADMIN_PASSWORD`, and `MASTER_ENCRYPTION_KEY`. Closes the QUICKSTART reference.
- **README** — added LICENSE / CHANGELOG / NOTICE entries to the documentation list.

**Drift caught while writing the env example (recorded for a follow-up ticket, not fixed in A9):** pydantic-settings parses `List[str]` env vars as JSON, so `CORS_ORIGINS=http://a,http://b` raises `JSONDecodeError` at startup. Today's `.env.example` uses the JSON-array form (`CORS_ORIGINS=["http://a","http://b"]`) which works, but `docs/CONFIGURATION.md` documents the comma-separated form, which doesn't. Proper fix is a `field_validator` on `Settings.cors_origins` that accepts both forms. Filed as a future task; out of scope for A9.

**Acceptance:** `cp backend/.env.example backend/.env` boots `Settings()` cleanly (verified via a temp-rename script that imported `Settings` and printed every nontrivial field); root `LICENSE`, `NOTICE`, and `CHANGELOG.md` exist. Backend test suite still 235 passed / 8 skipped.

---

### A10. Surface JSON parameter parse errors instead of silently dropping them — ✅ shipped (PR #31, branch `fix/query-params-error-surface`)

**Why:** `QueryEditor.tsx:getQueryParams` swallowed `JSON.parse` errors and returned `{}`. Users typing invalid params got "no rows" back with no indication that their query had been silently re-parameterised.

**Shipped:**

- **Parser:** `getQueryParams` now returns a discriminated union `QueryParamsResult = { ok: true; value: Record<string, unknown> } | { ok: false; error: string }`. The error string is the underlying `Error.message` (typically the engine's `SyntaxError` text, e.g. `"Expected property name or '}' in JSON at position 1"`). Per the explicit scope decision, no new shape validation was added — if `JSON.parse` succeeds, the value is returned as-is.
- **Editor UI** (only the param-related bits — no other markup churn):
  - Inline `role="alert"` caption under the params textarea: `Invalid JSON: <engine message>`. Wired via `aria-describedby` to the textarea and gated on `aria-invalid`.
  - Red border + red focus ring on the textarea when invalid.
  - Execute button: `disabled` + `aria-disabled` + tooltip `"Fix the invalid JSON in Parameters to enable Execute"` + screen-reader-only suffix on `aria-label`.
  - Shift+Enter (and Ctrl/Cmd+Enter) keyboard shortcut now no-ops when params are invalid, matching the disabled-button behaviour so power users get the same guard.
  - When the params panel is **closed** and params are invalid, a 10px red dot (`absolute -top-1 -right-1`) appears on the `Parameters` toggle button so the user understands why Execute is dimmed without having to expand the panel. Dot disappears once the panel is open (caption replaces it).
- **Call site:** `WorkspacePage.handleExecute` now checks `parseResult.ok` and bails on `false` rather than passing `{}` onward — defensive belt-and-suspenders since the editor already disables Execute / Shift+Enter, but ensures any future caller can't bypass the editor and silently re-parameterise the query.
- **Tests:** new `frontend/src/components/__tests__/QueryEditor.test.tsx` with 12 cases — 6 for the pure parser (including a regression test that explicitly forbids the old `→ {}` coercion) and 6 for the editor wiring (Execute disable, alert caption gating, dot visibility, Shift+Enter blocked-vs-allowed, ARIA attributes).

**Acceptance (verified):** typing `{bad` into the params textarea shows an inline red `Invalid JSON: …` caption, the Execute button is disabled with a tooltip, the toggle button shows a red dot when collapsed, Shift+Enter no longer fires the query. 12/12 new tests pass; full frontend suite still 50/50; backend regression suite still 235 passed / 8 skipped.

**Estimate:** 1 hour. **Actual:** ~30 min coding + tests + docs.

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
- [x] **A2** — Fix tab pin/unpin (PR #26 on `fix/tab-pin-unpin`; `onTabUnpin` wired through, pin button conditionally rendered as `tab.pinned ? onTabUnpin : onTabPin` so a parent supplying only one direction no longer renders a no-op button)
- [ ] **A3** — Add Pin / Hide actions in NodeContextMenu
- [x] **A4** — Remove the debug marker (or gate it on env) (PR #25 on `fix/graphview-debug-marker`; gated on `import.meta.env.DEV` with Vite ambient types added in `frontend/src/vite-env.d.ts`)
- [ ] **A5** — Enforce viz limits in WorkspacePage before rendering
- [ ] **A6** — Unify the label color palette
- [x] **A7** — Fix `expand_node` for `depth != 1` (PR #27 on `fix/expand-node-depth`; depth-2 now returns intermediate nodes via `nodes(path)`)
- [x] **A8** — Make the per-user rate limit actually fire (PR #29 on `fix/per-user-rate-limit`; resolves user via `session_manager.get_user_id` so the cookie can't drift from the manager)
- [x] **A9** — Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example` (PR #30 on `chore/license-changelog-env`; Apache-2.0 LICENSE + matching NOTICE, Keep-a-Changelog-style CHANGELOG seeded with 0.1.0, full env example covering every `Settings` key + `ADMIN_PASSWORD` with required-in-prod markers; verified that `cp backend/.env.example backend/.env` boots cleanly. Caught a doc/code drift along the way: pydantic-settings parses `List[str]` as JSON, so `CORS_ORIGINS` must be a JSON array even though `docs/CONFIGURATION.md` shows the comma form — recorded as follow-up)
- [x] **A10** — Surface JSON parameter parse errors instead of silently dropping them (PR #31 on `fix/query-params-error-surface`; `getQueryParams` now returns `{ ok, value } | { ok, error }`, the editor renders an inline `role="alert"` caption + red border under the params textarea, disables Execute with a tooltip, blocks Shift+Enter, and shows a red dot on the `Parameters` toggle when the panel is collapsed; 12 unit tests added)
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
