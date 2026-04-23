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

### A1. Wire the Settings modal (gear button + theme) — ✅ shipped (PR #36 on `feat/a1-settings-modal-and-theme`)

**Why:** `SettingsModal` exists and is importable but is never rendered open. `theme`, `defaultViewMode`, `queryHistoryLimit`, `autoExecuteQuery`, viz limits, table page size, default layout, and export format depend on it being reachable.

**Files & changes:**

- `frontend/src/pages/WorkspacePage.tsx`
  - Header (around line 333): add a gear `<button>` next to the Disconnect button that calls `setShowSettings(true)`. Use `aria-label="Open settings"`.
  - Around line 309: replace the hard-coded `bg-zinc-950 text-zinc-100` shell with classes derived from `useSettingsStore().theme` (`'dark' | 'light' | 'system'`). For `'system'`, key off `window.matchMedia('(prefers-color-scheme: dark)')`.
- `frontend/src/components/Layout.tsx` (lines 13–14): same theme-aware shell so non-workspace routes match.
- `frontend/tailwind.config.js`: enable `darkMode: 'class'` (currently implicit) and switch the workspace shell to `dark:bg-zinc-950 bg-white` style classes. Add a small `useTheme()` hook in `frontend/src/utils/` that toggles `document.documentElement.classList`.

**Acceptance:** Clicking gear opens `SettingsModal`. Toggling theme to `light` recolors the workspace background and text without reload.

**Status (PR #36):** Gear button rendered next to Disconnect with `aria-label="Open settings"`. New `useTheme()` hook (`frontend/src/utils/useTheme.ts`) toggles a `dark` class on `document.documentElement` based on `settingsStore.theme`, subscribes to `prefers-color-scheme` while in `auto` mode, and cleans up on unmount; mounted at the App root so all routes pick up the preference. Tailwind v4 doesn't use a `tailwind.config.js` (this project uses `@tailwindcss/vite` with zero-config), so the class-based override moved into `frontend/src/index.css` via `@custom-variant dark (&:where(.dark, .dark *));`. Repainted shell-level surfaces (`WorkspacePage` outer/header/query bar, `Layout` non-workspace shell, `App` LoadingFallback) with `dark:` pairs so theme changes apply without reload. 11 new unit tests (`useTheme.test.ts` + `SettingsModal.test.tsx`); full suite 119/119. **Scope cut:** leaf components (`TableView`, `QueryEditor`, `GraphView` canvas, `GraphControls` panels, `ConnectionPage`, `LoginPage`, `SettingsModal`'s own inline-styled inputs) keep their existing dark palette; full light-mode repaint is left as follow-up because it's a per-component design exercise rather than a refactor.

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

### A3. Add Pin / Hide actions in NodeContextMenu ✅ shipped

**Why:** `togglePinNode` and `toggleHideNode` exist in `graphStore` but are unreachable from the UI.

**Files & changes:**

- `frontend/src/components/NodeContextMenu.tsx`
  - Extend props with `onPin?(nodeId)`, `onHide?(nodeId)`, plus boolean `isPinned`, `isHidden` to label the action correctly ("Pin" vs "Unpin", "Hide" vs "Show").
  - Add two new menu buttons between Expand and Delete (lines ~134, ~135). Match existing style.
- `frontend/src/components/ResultTab.tsx` (the file that mounts `NodeContextMenu`): pass new handlers wired to `useGraphStore.togglePinNode` / `toggleHideNode`. Read `isPinned`/`isHidden` from the same store.
- `frontend/src/components/GraphView.tsx`: confirm pinned nodes draw a small visual indicator (e.g. ring stroke). It already uses `pinnedNodes` for force pinning (lines 299–304); just add CSS `stroke-width` change when `pinnedNodes.has(d.id)`.

**Acceptance:** Right-click a node → Pin → node stays put under force. Right-click → Hide → node and its edges disappear from view. Both reverse via the same menu.

**Estimate:** 2–3 hours.

**Status (2026-04-19, PR pending on `feat/a3-a5-pin-hide-and-viz-limits`):** shipped. `NodeContextMenu` props now accept `onPin?` / `onHide?` plus `isPinned` / `isHidden`; the menu renders four entries in the order Expand → Pin/Unpin → Hide/Show → Delete (each gated on its handler being supplied). The pin/hide buttons label-flip on the current state and expose `aria-pressed` so screen readers can read the toggle. `ResultTab` reads `pinnedNodes` / `hiddenNodes` / `togglePinNode` / `toggleHideNode` from `useGraphStore` and passes through the right state for the right `nodeId`. `GraphView` distinguishes pinned nodes with an amber stroke (`#f59e0b`, width 3), separate from the existing red (selected) and dark-blue (path) highlights; the existing simulation already honoured `pinnedNodes` for `fx`/`fy`, so the menu hits the working code path. Adds 8 unit tests on `NodeContextMenu` covering label flipping, conditional rendering, button ordering with all four handlers wired, and handler dispatch with the correct `nodeId`.

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

### A5. Enforce viz limits in WorkspacePage before rendering ✅ shipped

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

**Status (2026-04-19, PR pending on `feat/a3-a5-pin-hide-and-viz-limits`):** shipped. `WorkspacePage` now pulls `maxNodesForGraph` / `maxEdgesForGraph` from `useSettingsStore`, computes a single human-readable `vizDisabledReason` (`"Result has X,XXX nodes, exceeding the visualization limit of Y,YYY. ..."`) from the active tab's result counts, and force-flips the tab into `viewMode='table'` via a `useEffect` whenever the reason fires while the tab is on graph. The reason string is also passed to `ResultTab`, which generalised the existing `result.visualization_warning` plumbing into a unified `vizUnavailableReason` (server warning takes precedence; either source disables the Graph button + renders the banner). The banner now also exposes an "Open Settings" action when the reason is client-side, so the user can immediately raise the limit instead of hunting through the UI. Adds 5 unit tests on `ResultTab` covering banner rendering, button-disable, the Open-Settings affordance (rendered for client-side reasons but hidden for server-side warnings), and the no-reason baseline.

---

### A6. Unify the label color palette ✅ shipped

**Why:** `nodeColors.ts:LABEL_COLORS` is a fixed array indexed in **insertion order**, while `graphStyles.ts` uses `d3.scaleOrdinal(d3.schemeCategory10)` with **its own** insertion map. Same labels can get different colors in pill vs node depending on which is rendered first.

**Files & changes:**

- `frontend/src/utils/nodeColors.ts`: export `LABEL_COLORS` and the `getNodeLabelColor` map.
- `frontend/src/utils/graphStyles.ts`
  - Replace `const colorScale = d3.scaleOrdinal(d3.schemeCategory10)` with `import { getNodeLabelColor } from './nodeColors'` and have `getDefaultNodeColor` delegate.
- Add a unit test in `frontend/src/utils/nodeColors.test.ts` that asserts the same label resolves to the same color when called via both code paths.

**Acceptance:** Sidebar pill color for label `Person` matches the node circle color in the graph.

**Estimate:** 1 hour.

**Status (2026-04-19, PR pending on `fix/unify-color-palette`):** shipped. `graphStyles.ts` no longer instantiates its own `d3.scaleOrdinal`; `getDefaultNodeColor` is now a thin delegating wrapper around `getNodeLabelColor`, so the metadata-sidebar pill and the graph-canvas circle share one module-level insertion-order map and converge on the same hex for any given label regardless of which surface renders it first. `d3` import dropped from `graphStyles.ts` (it was only used for the colour scale). Added a dedicated `frontend/src/utils/graphStyles.test.ts` with 7 regression tests pinning the contract: parity between `getDefaultNodeColor` and `getNodeLabelColor`, parity through `getNodeStyle({}, ...)`, both call orders (graph-first then sidebar-first, and vice versa), hex shape, distinctness across labels, and that user-supplied `nodeStyles` overrides still win. Also pruned the now-dead `scaleOrdinal` / `schemeCategory10` mocks from `GraphView.test.tsx`. 66/66 frontend tests green; no new tsc or eslint issues introduced.

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

#### Phase 2 — Camera focus on newly-added neighbourhood ✅ shipped

**Status:** Shipped on `feat/a11-camera-focus-and-isolate` (bundled with phase 3 in PR #35). `graphStore` gained `cameraFocusAnchorIds: string[]` plus `setCameraFocusAnchorIds` (which dedups its input) and `clearCameraFocusAnchorIds` (which preserves the array reference when already empty so subscribers don't re-render). `WorkspacePage.handleExpandNode` was changed to return the merge result and `handleDoubleClickNode` now sets the anchor union `[clickedNodeId, ...merged.addedNodeIds]` after `await`. `GraphView` watches the field via a new `useEffect` (deps include `filteredNodes` so it runs *after* the main mount effect rebuilds the simulation) that defers one animation frame, reads positions from `simulationRef.current.nodes()`, computes the anchor bounding box, animates `d3.zoomIdentity` with `transition().duration(400)`, briefly pins the clicked node for 2s, then clears the anchors on `transition().on('end')`. Single-anchor / tightly-clustered cases are handled by flooring content size at 200px and clamping `scale ∈ [0.3, 2.0]` so the zoom doesn't max out on a zero-area box. Honours `pinnedNodes` — the 2s auto-release won't unpin a user-pinned node. Adds 6 unit tests on the new store actions.

#### Phase 3 — Explicit reversible "isolate" mode ✅ shipped

**Status:** Shipped on `feat/a11-camera-focus-and-isolate` (bundled with phase 2 in PR #35). `NodeContextMenu` gained an `onIsolateNeighborhood?` prop and a new `Show only this & its neighbourhood` entry rendered between Hide and Delete (with `aria-label="Show only node {id} and its neighbourhood"`). `queryStore` gained `previousGraphElements: GraphElements | null` on `QueryTab` plus two actions: `isolateNeighborhood(tabId, nodeId)` snapshots the current `result.graph_elements`, then filters to the clicked node + every edge incident to it + those edges' endpoints (deterministic client-side filter, no API call); `restoreGraphElements(tabId)` puts the snapshot back and nulls the field. `isolateNeighborhood` is a no-op while a snapshot is already held so re-isolating can't clobber the original canvas. `ResultTab` reads `tab.previousGraphElements` to render a `← Back to full result` breadcrumb above the canvas; the breadcrumb only shows when both the snapshot and an `onRestoreFullResult` handler are present, so omitting the handler hides the affordance entirely. The Isolate menu entry is also hidden while in isolate mode for the same reason. Snapshots are dropped from `persist`'s `partialize` (they're a view of `result`, which is already dropped). Adds 7 store tests + 3 menu tests + 4 ResultTab breadcrumb tests.

---

## Milestone B — CI and production deployment are real

Bigger but well-scoped. Listed as headline tickets here; expand into A-style detail when starting. **Total: ~2 weeks for one engineer.**

### B1. GitHub Actions: `backend-ci.yml` — ✅ partial (PR #37 on `feat/b1-b2-ci-tests-and-lint`, bundled with B2)

- Jobs: `lint` (ruff + black + mypy), `unit` (pytest, no DB), `integration` (AGE service + `alembic upgrade head` + `pytest -m integration`, `USE_REAL_TEST_DB=true`).
- Service image: `apache/age:dev_snapshot_PG16` (Docker Hub does not publish `PG16_latest`; this tag tracks PG16 + AGE).
- Cache `~/.cache/pip` and `backend/venv`.

**Status (PR #37):** `lint` (ruff only) and `unit` jobs shipped. Path-filtered to `backend/**`, Python 3.11 with pip cache, concurrency-cancellation enabled. Pre-existing ruff debt fully cleared so the gate is green from day one (38 autofixes + 3 dead-variable deletions in `app/api/v1/auth.py`, `app/api/v1/session.py`, `app/core/validation.py`). 234/234 unit tests run on every push/PR. Three sub-tickets carved out for follow-up so this PR didn't balloon:

- **B1.1** — ✅ shipped in PR #40 (bundled with B8). Ran `black app tests` across the backend tree using the existing `[tool.black]` config in `backend/pyproject.toml` (line-length 100, target-version py311); 67 files reformatted, 8 unchanged, net −49 lines, zero behavioural deltas. The reformat is isolated in a single `style(backend): apply black ...` commit so `git blame --ignore-revs` can suppress it cleanly. The `# - name: black --check` step in `.github/workflows/backend-ci.yml` is now uncommented and runs alongside `ruff check .` on every push/PR. Post-reformat verification: `ruff check .` clean, `pytest -m "not integration and not performance"` still 238 passed / 1 skipped / 8 deselected.
- **B1.2** — ✅ shipped (PR on `feat/b1.2-mypy-ci`). Lint job runs `mypy app` on Python 3.11. **Syntax:** a comment in `app/core/metrics.py` used `# type: …`, which mypy parses as a type comment — reworded. **Types:** fixes across `agtype`, `connection`, `utils.first_value` (tuple + dict rows), `metadata` stats dict, `session`/`auth` session id + user id narrowing, `graph` expand (avoid shadowing `node_id` path param), `errors` handler registration (`# type: ignore[arg-type]` for APIException subtype contravariance), `connection` fetchall cast. **`warn_return_any`** set to `false` in `pyproject.toml` — FastAPI/Starlette still surface `Any` at boundaries; re-enable when those call sites are tightened (documented in config comment).
- **B1.3** — ✅ shipped (PR on `feat/b1.3-integration-ci`). Third job in `backend-ci.yml`: `services.age` uses `apache/age:dev_snapshot_PG16` (health-checked with `pg_isready`), env block sets `USE_REAL_TEST_DB=true` plus `TEST_DB_*` and `DB_*` at `localhost:5432` (runner jobs without a `container:` key reach the service via the published port, not the `services.age` DNS name), step order is `pip install -r requirements-dev.txt` → `alembic upgrade head` → `pytest -m integration --no-cov`. Audited `connected_client`: the real-DB path no longer opens a throwaway `DatabaseConnection` before `POST /session/connect` (that leaked a second pool); teardown calls `POST /session/disconnect`. `test_db_config` now reads the same `TEST_DB_*` env vars with defaults matching the official `apache/age` image (`postgres`/`postgres` on 5432). **`DatabaseConnection._configure_age`:** pool `configure` callbacks must leave the connection idle — psycopg runs with `autocommit=False`, so the `SELECT`/`LOAD`/`SET` sequence left the backend connection `INTRANS`; psycopg_pool discarded every new connection and `pool.wait()` timed out (`pool initialization incomplete after 30 sec`). Fix: `await conn.commit()` after the cursor block. `test_database_connection.py` updated for the pool API (`_pool` not `_conn`) and for `transaction()`-based rollback coverage (removed nonexistent `begin_transaction` / `rollback_transaction`). Docker Hub tag note: `PG16_latest` does not exist; `dev_snapshot_PG16` is the pinned PG16-family image.

### B2. GitHub Actions: `frontend-ci.yml` — ✅ shipped (PR #37, bundled with B1)

- `lint` (eslint), `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `build` (`vite build`).
- Cache `~/.npm` keyed by `package-lock.json`.

**Status (PR #37):** all four jobs shipped, path-filtered to `frontend/**`, Node 20 with npm cache, concurrency-cancellation enabled. Pre-existing tsc + eslint debt cleared so the gate is green from day one:

- 4 tsc errors fixed: `GraphView.tsx` widened `getEdgeStyle`/`getEdgeCaption` `edgeWidthProperty` to `string | null | undefined` to accept `edgeWidthMapping.property`; `ResultTab.test.tsx` GraphNode literal completed with `properties` + `type`; `GraphView.test.tsx` unused `name` → `_name`; `api.test.ts` `global.sessionStorage` → `globalThis.sessionStorage`.
- 3 eslint errors + 3 warnings handled via inline `// eslint-disable-next-line` directives with one-line justifications: 7 pre-existing `@typescript-eslint/no-explicit-any` sites (`apiCache.ts` cache map, `graphStyles.ts` d3 scale type ×2, `SettingsModal.tsx` select cast, `GraphView.tsx` d3-force teardown, `GraphView.test.tsx` simulation/selection mocks ×3); 2 intentional mount-only `useEffect`s (`WorkspacePage.tsx`, `MetadataSidebar.tsx`); 1 `react-refresh/only-export-components` co-location (`getQueryParams` in `QueryEditor.tsx`).
- Added `argsIgnorePattern: '^_'` + `varsIgnorePattern: '^_'` to `.eslintrc.cjs` so `_`-prefixed unused args are accepted as the convention.

The `--max-warnings 0` ratchet stays in place; the `no-explicit-any` rule stays at `error` severity. Each disable-next-line carries a comment explaining why, so reviewers can audit the ratchet's edges.

### B3. GitHub Actions: `container.yml` — ✅ shipped (PR #38 on `feat/b3-b4-b5-container-images`, bundled with B4+B5)

- Build both images on tag pushes; push to Docker Hub as `<namespace>/kotte-backend` and `<namespace>/kotte-frontend`.
- `trivy image` scan with severity `HIGH,CRITICAL` failing the build.

**Status (PR #38):** `.github/workflows/container.yml` shipped. Target registry is **Docker Hub** (not GHCR) so images land alongside the author's other projects (e.g. `viper`) and users can `docker pull <namespace>/kotte-{backend,frontend}` without a registry prefix. Triggers split across three paths: tag pushes matching `v*` go through the full build + Trivy scan + push pipeline; `workflow_dispatch` accepts `image_tag` + optional `push_latest` inputs for on-demand backfills; PRs that touch the Dockerfiles / `nginx.conf` / the workflow itself / `backend/requirements.txt` / `frontend/package-lock.json` go through the build + Trivy scan path only (`push: false`, `load: true` so Trivy can see the image) — this is what catches Dockerfile regressions before a release cut. Matrix strategy over `{backend, frontend}` so both images are handled in parallel with separate GHA layer-cache scopes. Trivy v0.35.0 with `severity: HIGH,CRITICAL`, `exit-code: 1`, `ignore-unfixed: true` (so CVEs without vendor fixes don't block merges — those belong in a base-image-bump PR instead). Tag computation via `docker/metadata-action` (semver major.minor.patch + major.minor + short sha + `latest` on the default branch + `pr-<N>` for PRs + raw `image_tag`/optional `latest` on dispatch). `permissions: {contents: read}` only — no package-write scope needed since we're not using GHCR. Docker Hub login gated on `github.event_name != 'pull_request'` so fork PRs skip auth (secrets aren't exposed to forks). Required secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. Optional variable `DOCKERHUB_NAMESPACE` overrides the publish namespace for org-owned accounts; defaults to `DOCKERHUB_USERNAME`. All third-party actions pinned to commit SHAs (checkout 4.2.2, setup-buildx 3.12.0, login 3.7.0, metadata 5.7.0, build-push 6.19.2, trivy-action 0.28.0) for supply-chain hygiene, matching the convention used in the `viper` repo.

### B4. Multi-stage backend image — ✅ shipped (PR #38, bundled with B3+B5)

- `deployment/backend.Dockerfile`: stage 1 `python:3.11-slim` builder with build deps + `pip install --target=/app/site-packages`; stage 2 `python:3.11-slim` runtime, copy site-packages and source, `USER kotte`, `HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health`.

**Status (PR #38):** `deployment/backend.Dockerfile` rewritten as the two-stage pattern above. Builder stage installs `build-essential` + `libpq-dev` and runs `pip install --no-cache-dir --target=/install -r requirements.txt`; runtime stage has only `libpq5` + `curl` plus the copied `/install` tree (`COPY --from=builder /install /app/site-packages`, with `PYTHONPATH` + `PATH` set so uvicorn's console script resolves). Non-root `kotte` user created with `/usr/sbin/nologin` as its shell. `HEALTHCHECK` uses `curl --fail --silent --show-error` with interval/timeout/retries tuned for a FastAPI startup (`--interval=30s --timeout=5s --start-period=15s --retries=3`). Both stages upgrade `pip` / `setuptools` / `wheel` so the bundled metadata from `python:3.11-slim` (which Trivy flags HIGH for CVE-2026-24049 on `wheel` and CVE-2026-23949 on `jaraco.context` via setuptools) is patched; the runtime stage also runs `apt-get upgrade -y` before installing libpq5/curl so the Debian libssl / openssl patch for CVE-2026-28390 ships with the image rather than blocking the Trivy gate. Validated locally: the image builds via `docker build`, the container boots, and `GET /api/v1/health` returns `{"status":"healthy","version":"0.1.0", ...}`. Final runtime image ~400 MB; the builder stage (~600 MB with gcc + headers) is thrown away after the `COPY --from=builder`, so the build tools never reach production.

### B5. Multi-stage frontend image (production) — ✅ shipped (PR #38, bundled with B3+B4)

- New file `deployment/frontend.Dockerfile.prod`: stage 1 `node:20-alpine` runs `npm ci` + `npm run build`; stage 2 `nginx:alpine` with a custom `nginx.conf` doing SPA fallback + gzip + cache headers. Expose 80.
- Keep current `frontend.Dockerfile` for dev compose.

**Status (PR #38):** `deployment/frontend.Dockerfile.prod` (new) and `deployment/nginx.conf` (new) shipped. The existing `deployment/frontend.Dockerfile` is untouched so `deployment/docker-compose.yml` continues to work for local dev with HMR on port 5173. Prod image uses `node:20-alpine` as the builder (matches the version `frontend-ci.yml` runs against), runs `npm ci --no-audit --no-fund` + `npm run build`, then hands only the `dist/` tree to `nginx:alpine`. Runtime image ~64 MB (vs. backend's ~400 MB). The nginx config drops the default server block, sets `server_tokens off`, turns on gzip above 1 KB for JS/CSS/JSON/XML/wasm, and encodes three routing rules: `/assets/*` gets `Cache-Control: public, max-age=31536000, immutable` (safe because vite hashes filenames), `/index.html` gets `Cache-Control: no-cache, no-store, must-revalidate` (so deploys propagate instantly), and everything else falls through `try_files $uri $uri/ /index.html` so React-router sub-routes survive a hard refresh. Static hardening headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`) added at the `server {}` level — these overlap partially with `SecurityHeadersMiddleware` on the backend but cover the static-response path where FastAPI isn't in the chain. Validated locally: image builds, SPA fallback works (`/workspace/anything` returns 200 + index.html content), the asset response carries a single `Cache-Control` header (not two — earlier draft had `expires 1y` + `add_header Cache-Control` which emitted both), and gzip is active for JS/CSS responses when the client sends `Accept-Encoding: gzip`.

### B6. Compose split — ✅ shipped (PR #39 on `feat/b6-compose-split`)

- `deployment/docker-compose.dev.yml` (current behavior, source mounts).
- `deployment/docker-compose.prod.yml` (uses `Dockerfile.prod`, `ENVIRONMENT=production`, secrets via `--env-file`, `restart: unless-stopped`, no source mounts, `mem_limit`/`cpus` per service).

**Status (PR #39):** legacy `deployment/docker-compose.yml` removed; replaced by two explicit files. `docker-compose.dev.yml` preserves the pre-split default behaviour but wires live-reload properly: `../backend/app` is bind-mounted onto `/app/app` (so `/app/site-packages` and `/app/data` — the credential store volume and the deps tree from the builder stage — stay untouched), the backend `command:` is overridden to `uvicorn ... --reload --reload-dir /app/app`, and the frontend uses the standard anonymous-volume trick (`../frontend:/app:rw` + `/app/node_modules`) so vite HMR works without the host's platform-mismatched `node_modules` shadowing the image's. `docker-compose.prod.yml` uses `frontend.Dockerfile.prod` (nginx serving the built SPA on port 80) + `backend.Dockerfile`, pulls secrets from `deployment/.env.prod` via `env_file`, adds `restart: unless-stopped` + per-service `mem_limit` / `cpus` (age 1 GB / 1.5 CPU, backend 512 MB / 1.0 CPU, frontend 64 MB / 0.5 CPU), marks the nginx container `read_only: true` with tmpfs mounts for `/var/cache/nginx`, `/var/run`, `/tmp` (deliberately omitting the Docker-only `:uid=101,gid=101` options for podman compatibility), and stops exposing AGE on the host. `deployment/.env.prod.example` documents the four required keys; the live `.env.prod` is gitignored. Six new Makefile targets (`compose-{up,down,logs}-{dev,prod}` + `compose-build-prod`) wrap the raw `docker compose` incantations; the prod targets fail fast if `.env.prod` is missing. Validated locally: both files pass `docker-compose config`; prod frontend container starts under `--read-only` + tmpfs and serves SPA fallback correctly; dev backend bind-mount doesn't clobber site-packages (`import fastapi` and `from app.main import app` both work); `watchfiles` is in the image so `--reload` uses native inotify. Known limitation carried forward: the shipped nginx serves static assets only — no `/api/*` reverse proxy — so real production deployments need either an external reverse proxy (Caddy/Traefik/Cloudflare) or a `VITE_API_BASE_URL` rebuild with `CORS_ORIGINS` widened. Tracked as a future enhancement, not a B6 follow-up ticket.

### B7. Migrations system — ✅ shipped (PR #41 on `feat/b7-alembic-migrations`)

- Add `alembic` to `backend/requirements.txt`; init under `backend/alembic/`.
- First migration: schema-bootstrap that creates AGE extension, runs the index-creation logic from `backend/scripts/migrate_add_indices.py`, and adds a future `users` table stub.
- New Make target `migrate-up`.

**Status (PR #41):** Alembic is in, but the scope diverged from the ticket's original wording in one deliberate way — **label-index creation is not part of the migration chain**. The reason is structural: `scripts/migrate_add_indices.py` walks runtime catalog state (`ag_catalog.ag_graph` + `ag_catalog.ag_label`) and creates indices on whatever labels exist _right now_. A static alembic migration would be frozen at authoring time and miss every label added afterwards, which is the norm rather than the exception in a graph DB. So the script stays (reachable now as `make reindex-labels`) and the alembic chain carries only the bits that are actually version-able.

Shipped pieces:

- **`backend/alembic/`** scaffolded — `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`, plus a README pointing at `docs/MIGRATIONS.md`. The `env.py` is rewritten from the default scaffold so it reads connection params from the **same `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` env vars that `scripts/migrate_add_indices.py` already uses**, with a fallback chain that lets operators override with `-x url=...` or `ALEMBIC_SQLALCHEMY_URL`. `target_metadata = None` by design — the app has no ORM, every migration is hand-written raw SQL via `op.execute(...)`, and `--autogenerate` would produce nothing useful. Driver is `postgresql+psycopg://…` to match the rest of the backend's psycopg3 stack; SQLAlchemy is pulled in only as alembic's engine façade (in `requirements-dev.txt` + the `dev` extra — **not** in `requirements.txt`, so the runtime image stays lean). The alembic.ini `sqlalchemy.url` is left as the `driver://...` placeholder on purpose; `_resolve_url()` detects that sentinel and falls through to env vars.
- **Migration `2c3c565210b1` — enable age extension.** Single statement: `CREATE EXTENSION IF NOT EXISTS age`. No-op on databases where AGE is already installed (the common case). Downgrade is deliberately a no-op because `DROP EXTENSION age CASCADE` would delete every graph in the DB — a data-loss operation that should never happen via a routine `alembic downgrade`. Documented in the migration docstring.
- **Migration `78c03fa27fda` — create kotte users stub.** Creates an empty `kotte_users(id BIGSERIAL PK, username CITEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(), last_login_at TIMESTAMPTZ NULL)` table plus the `citext` extension it depends on. **The app does not read from this table yet** — it's forward-plumbing for Milestone D1's multi-user work, so the PR that actually wires authentication isn't simultaneously landing a new migration + new code + a rollout story. Every new table in this chain carries the `kotte_` prefix so it can't collide with whatever schema the target DB already has (many AGE databases share a Postgres instance with unrelated apps that have their own `users` table). Downgrade drops the table cleanly; `citext` is intentionally left installed.
- **Makefile** grows six migration targets: `migrate-up` (`alembic upgrade head`), `migrate-down` (`alembic downgrade -1`), `migrate-current`, `migrate-history`, `migrate-new MSG="..."` (scaffolds a new revision — no `--autogenerate`), and `reindex-labels` (runs the catalog-walking script). The help output groups them under a new "Migrations" block. `migrate-new` refuses to run without an explicit `MSG=` so we can't land a nameless `_.py` file by accident.
- **`scripts/migrate_add_indices.py` docstring rewritten** to position the script as complementary to alembic, with the table explaining when to reach for which tool. The script itself is unchanged — it's still the right answer for "new labels just appeared, reindex please".
- **`docs/MIGRATIONS.md` (new)** — full operator guide covering the mental model (Kotte doesn't own a database), the URL-resolution fallback chain, both shipped migrations, how to add a new one (raw SQL + `IF NOT EXISTS` ground rules), offline SQL review, and known limitations (no runtime hook, no autogenerate, needs `CREATE EXTENSION` privilege on the target role).
- **No runtime hook**, deliberately. The ROADMAP's original sketch mentioned "entrypoint hook that runs `alembic upgrade head` before uvicorn (opt-in via `RUN_MIGRATIONS=true` so dev isn't forced through it)". That shape made sense when I first wrote B7; closer reading of the codebase revealed it doesn't match Kotte's architecture. Kotte connects to _many_ databases (one per user login), not one — a startup hook would have to know _which_ database to migrate, and blanket-migrating whatever shows up would surprise users who reuse databases across tools. Also, production AGE roles often lack `CREATE EXTENSION` privileges, so the hook would either fail loudly on every login or silently fail. Decoupling deploy from schema change is the right call; a `RUN_MIGRATIONS=true` hook against a specific `KOTTE_MIGRATION_DB_URL` is easy to add later if a single-DB deployment wants it. Documented as a known limitation in `docs/MIGRATIONS.md`.

Validated end-to-end against a fresh `apache/age:latest` container on port 5433:
- `alembic upgrade head` → both migrations apply cleanly; `age 1.7.0` + `citext 1.8` present in `pg_extension`; `kotte_users` has the exact 5 columns with correct NOT-NULL / unique / PK constraints; `alembic_version` pinned at `78c03fa27fda`.
- `alembic downgrade -1` → `kotte_users` dropped cleanly (`to_regclass('public.kotte_users')` returns NULL); `alembic_version` rewinds to `2c3c565210b1`.
- `alembic upgrade head` (second run) → re-applies the second migration cleanly.
- `alembic upgrade head` (third run, already at head) → no-op, zero log lines.
- `alembic upgrade head --sql` (offline mode) → produces a reviewable transaction block that a DBA can paste into `psql -f`.

Follow-ups tracked elsewhere:
- `RUN_MIGRATIONS=true` entrypoint hook for single-DB deployments — enhancement, not a B7 sub-ticket (no open follow-up yet).
- `kotte_sessions` / `kotte_saved_connections` migrations land alongside the Milestone D features that actually use them.

### B8. Pre-commit — ✅ shipped (PR #40 on `feat/b1.1-b8-black-and-precommit`, bundled with B1.1)

- `.pre-commit-config.yaml` with hooks: `ruff --fix`, `black`, `prettier` (frontend), `eslint`, `trailing-whitespace`, `check-yaml`, `cspell`.
- README note: `pre-commit install`.

**Status (PR #40):** `.pre-commit-config.yaml` shipped at the repo root with three repo groups. `pre-commit/pre-commit-hooks v6.0.0` for generic hygiene — `trailing-whitespace` (with `\.md$` excluded because markdown hard-breaks rely on them), `end-of-file-fixer`, `check-yaml --allow-multiple-documents`, `check-json` (scoped to skip `frontend/tsconfig*.json` — those are JSONC files with comments + trailing commas that Python's stdlib can't parse; tsc + vite are the real consumers so strict validation is redundant), `check-toml`, `check-merge-conflict`, `check-added-large-files --maxkb=500`, `mixed-line-ending --fix=lf`. `psf/black-pre-commit-mirror 26.3.1` running `black --config backend/pyproject.toml` scoped via `files: ^backend/(app|tests|scripts)/` so the canonical 100-char py311 config is reused (no dual source of truth). `astral-sh/ruff-pre-commit v0.15.11` running `ruff --fix` with the same scoping + config reuse. Plus a `local` hook for frontend eslint that shells out to `npx eslint --max-warnings 0` on staged `frontend/**/*.{ts,tsx}` paths, stripping the `frontend/` prefix before cd-ing in so `.eslintrc.cjs` + `frontend/node_modules/` resolve correctly — kept as a local (non-mirror) hook to reuse the already-installed plugin set (`@typescript-eslint`, `react-hooks`, `react-refresh`) rather than pinning a duplicate copy in pre-commit's cache. `default_language_version.python` is deliberately *not* pinned to 3.11 — black's output is determined by its own version + `[tool.black] target-version`, not by the Python running it, and pinning here locks contributors on 3.10 / 3.12 / 3.13 out of `pre-commit install` for no canonical-output benefit (CI still enforces py311). Dev dependency: `pre-commit>=3.5.0` added to `backend/requirements-dev.txt` and the matching `dev` extra in `pyproject.toml` so `make install-backend` pulls it. Three new Makefile targets: `install-hooks` (wraps `pre-commit install` — the one-time setup step), `precommit-run` (`pre-commit run --all-files` for whole-tree verification), `format-backend` (black convenience without the hook). Hygiene auto-fixes from the first `pre-commit run --all-files`: 9 files with trailing whitespace + 28 files missing a trailing newline, fixed in place and committed alongside the config. Incidental cleanup: `frontend/test-results/.last-run.json` (Playwright last-run state file) was tracked in git by accident — removed with `git rm --cached` and `frontend/test-results/` + `frontend/playwright-report/` added to `.gitignore`. Validated: fresh `pre-commit install` + `pre-commit run --all-files` → all 11 hooks green; post-whitespace-fix backend unit suite still 238 passed.

### B9. Doc reconciliation pass (no code changes, just docs)

- `docs/CONFIGURATION.md`: drop unimplemented `sqlite`/`postgresql`/`redis` credential backends, or move them to a "Roadmap" section.
- `docs/QUICKSTART.md`: rewrite the "Next Steps" so it doesn't read like the visualizer is unbuilt.
- `docs/ARCHITECTURE.md`: change `app/core/security.py` references to `app/core/middleware.py`, `app/core/auth.py`, `app/core/credentials.py`.
- `docs/KUBERNETES_DEPLOYMENT.md`: add a banner "Status: planned, not shipped" until manifests land.

**Status (2026-04-19, PR pending on `docs/sync-post-a10`):** all four bullets above shipped, plus REVIEW.md was strikethrough-updated for A2/A4/A10 (and §3/§4 annotated for A2/A4 done), `CONFIGURATION.md` got a `CORS_ORIGINS` JSON-array correction (the live shape `pydantic-settings` actually accepts), and the "Suggested execution order" section above got a status-note pointer at the progress checklist. CHANGELOG `[Unreleased]` records the doc sync. The remaining open follow-up under this banner is the `Settings.cors_origins` validator that would accept both comma-separated and JSON-array forms — that one is a code change, tracked separately.

---

## Milestone C — Make it a graph product

What moves Kotte from "feature complete v0.1" to something a user would prefer over `psql` + Cytoscape. **Total: ~3–4 weeks for one engineer.**

### C1. CodeMirror 6 Cypher editor

- **Shipped:** `@neo4j-cypher/codemirror` + `@uiw/react-codemirror` + `codemirror` 6; Neo4j stylesheet; `QueryEditor.tsx` uses CodeMirror instead of a `<textarea>`. History / Shift+Enter / Escape keybindings stay wired via `useQueryEditorKeyboard` and `EditorView#hasFocus`.
- **Shipped (schema completion):** `MetadataSidebar` loads `/graphs/.../metadata` into `useGraphStore().graphMetadata` (not persisted). `graphMetadataToEditorSchema()` maps node labels, edge labels, and unioned property keys into `EditorSupportSchema`; `applyCypherEditorSchema()` calls `getStateEditorSupport(view.state)?.setSchema(...)` (Vite + TS aliases: `neo4j-cypher-cm-state-selectors`, because the package omits that path from `exports`). Suggestions update when the user switches graphs or metadata refreshes.

### C2. Visualization upgrades

**Goal:** Make the force-directed graph readable at a glance (direction, density, self-edges) and scale past “SVG comfort” without rewriting `ResultTab` / store contracts.

**Current baseline (2026):** `GraphView.tsx` uses d3-force and draws links as SVG `<line>` elements (`container.selectAll('line')` under a `.links` group). Nodes are circles; zoom lives on the SVG container. Edge color/width comes from `getEdgeStyle` + path highlights. No arrowheads, no curves, no alternate renderer.

#### Recommended delivery order

Work top-to-bottom; each phase is shippable on its own.

| Phase | Scope | Rationale |
|-------|--------|-----------|
| **C2.1** | Arrowheads + marker strategy | **Shipped (2026-04):** `<defs>` + `markerUnits="userSpaceOnUse"`; one marker per distinct edge stroke color (`markerIdForColor`); `marker-end` on link paths. |
| **C2.2** | Curved links + parallel-edge offset | **Shipped (2026-04):** `graphLinkPaths.ts` — quadratic Bézier, control-point offset by parallel index among directed `(source,target)` groups; endpoints shortened by node radii. |
| **C2.3** | Self-loops | **Shipped (2026-04):** same module — symmetric loop above node; stacked offsets when multiple self-edges share a node. |
| **C2.4** | Canvas / Pixi fallback | Gate on `nodes.length` (and optionally `edges.length`) — align with `settingsStore` `maxNodesForGraph` story so the threshold is user-tunable later. Same `GraphViewProps`; internally `GraphView` chooses SVG vs `GraphCanvas`. |
| **C2.5** | Minimap | Read node positions from the same simulation (or shared ref); render a coarse overview; `d3-zoom` transform sync (brush or drag on minimap). |
| **C2.6** | Lasso multi-select | `d3-brush` (or polygon lasso) with modifier key; selection feeds `useGraphStore` or local selection callback — **decide in implementation** whether lasso adds to `selectedNode` / pin set or only highlights; document behaviour in `ARCHITECTURE` or `GraphControls`. |

#### C2.1 — Arrowheads (technical)

- Add a single `<defs>` block on the SVG (or one per mount in `GraphView`’s effect) with `<marker>` elements. Prefer **`markerUnits="userSpaceOnUse"`** so stroke width and zoom behave predictably; set `refX` / `refY` so the tip meets the **target node rim** (account for node radius ~ stroke).
- **Color:** Either one neutral marker + `marker-end` cannot vary per edge easily — typically use **one marker per distinct edge color** (id e.g. `arrow-${hash(color)}`) or use SVG **`context-stroke`** / currentColor tricks if browser support is acceptable. Pragmatic approach: quantize edge colors to a small palette + path/highlight overrides, or generate markers for the finite set of styles returned by `getEdgeStyle`.
- **Hit-testing:** Widen invisible stroke on paths for `onEdgeClick` (already a pattern for thick edges).

#### C2.2 — Curves + parallel edges (technical)

- Replace straight segments with a **quadratic Bézier** (one control point perpendicular to the chord mid-point). For **parallel edges** between the same ordered pair `(sourceId, targetId)`:
  - Group edges by key `min(s,t)+'|'+max(s,t)` for undirected offset sign, or keep directed `(sourceId, targetId)` if arrows must stay asymmetric.
  - Assign each edge an **index** `i` in `[0, k-1]`; offset control point by `(i - (k-1)/2) * separation` (constant in user-space px, scaled if needed).
- **Simulation:** Keep using `forceLink` with center distance; curves are presentation-only (update `d` on tick).

#### C2.3 — Self-loops (technical)

- When resolved `source === target`, draw an arc from the node surface, out and back (e.g. control point offset by `(0, -radius-offset)`). Ensure arrowhead orientation matches traversal direction if the data model implies one.

#### C2.4 — Canvas / Pixi (technical)

- **Contract:** `GraphCanvas.tsx` (name as needed) receives the same props as `GraphView`; no changes to `ResultTab` beyond optional size props already passed.
- **State:** Share layout positions: either run the same d3 simulation and pass positions to canvas, or extract a `useGraphLayout` hook used by both (harder but cleaner).
- **Interactivity:** Reimplement pick (node/edge), zoom/pan (d3-zoom on overlay or Pixi viewport), and context menu coordinates — budget extra time; this is the largest phase.
- **Threshold:** Start with a constant (e.g. 1500 nodes) + console-free degradation; wire to settings in a follow-up if C2.4 runs long.

#### C2.5 — Minimap (technical)

- Secondary SVG or canvas; clone node positions at low frequency (on simulation `end` or throttled `tick`). Show viewport rectangle from inverse of current zoom transform. Click/drag on minimap → `zoom.transform`.

#### C2.6 — Lasso (technical)

- Gate on **modifier + drag** (e.g. Shift) so pan/zoom stays default. Brush end → compute nodes inside polygon → call store or props. Avoid conflicting with node drag if added later.

#### Acceptance (whole C2)

- Directed queries: edges show **clear direction** (C2.1) without heads obscuring labels.
- Multi-edge between two nodes: **visually separable** (C2.2).
- Self-relationships: **visible** (C2.3).
- With N above threshold: UI remains **usable** (pan/zoom/select) via canvas path (C2.4).
- Optional: minimap and lasso behave without breaking existing **pin, hide, expand, export** flows.

#### Non-goals for C2 (defer)

- 3D graph, temporal animation, or full graph analytics layout suite.
- Backend changes (C2 is frontend visualization only unless streaming positions from server is requested later).

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

> **Status note (2026-04-20):** the week-numbered plan below was the original sequencing proposal. Actual progress is tracked in the **[Progress checklist](#progress-checklist)** below — that's the authoritative source for what's done. As of this writing, **all of Milestone A is shipped** (A1–A11 inclusive), **B1+B2 shipped in PR #37** (B1 partial — B1.1/B1.2/B1.3 sub-tickets deferred so the day-one CI gate stays green rather than gating on pre-existing debt), **B3+B4+B5 shipped in PR #38** (the "container images + Docker Hub publish pipeline" trio — multi-stage Dockerfiles for both services, nginx config with SPA fallback + gzip + cache headers, tag-triggered GHA workflow that builds, Trivy-scans, and pushes to Docker Hub as `<namespace>/kotte-{backend,frontend}` — matches the registry convention used by the rest of the author's projects), and **B6 shipped in PR #39** (compose split — dev file with source mounts / `uvicorn --reload` / vite HMR, prod file with nginx SPA serving / `restart: unless-stopped` / per-service resource limits / `read_only` nginx + tmpfs / secrets via `env_file`, plus six Makefile targets). After PR #39 landed, PR #40 shipped the **B1.1 + B8** pair (backend black reformat + pre-commit hooks — the one-time 67-file reformat was isolated in a single `style(backend): ...` commit so `git blame --ignore-revs` can hide it cleanly, the `black --check .` gate in `backend-ci.yml` is now live, and the repo-root `.pre-commit-config.yaml` wires black / ruff / eight hygiene hooks / a local frontend-eslint hook so the CI gate mirrors into the developer's `git commit` path). PR #41 shipped **B7** (Alembic migration chain — `backend/alembic/` scaffolded with DB_*-driven URL resolution, two revisions landing the AGE extension and the `kotte_users` stub table, label-index creation deliberately kept as an operational script because it depends on runtime catalog state, full operator guide at `docs/MIGRATIONS.md`, no runtime hook so per-login connections aren't surprised — documented as a known limitation). **B1.3** followed (integration CI — third `backend-ci.yml` job with `apache/age:dev_snapshot_PG16`, `alembic upgrade head`, `pytest -m integration`, plus a pool `configure` fix: `commit` after AGE setup so psycopg_pool reaches `min_size`). **Milestone B** checklist is complete (B1–B9). Smaller related tickets are bundled into one PR (A3+A5 as the "graph-canvas safety" pair; A11.2+A11.3 as the "double-click follow-through" pair; B1+B2 as the "CI for tests and lint" pair; B3+B4+B5 as the "container images + Docker Hub publish" trio).

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

- [x] **A1** — Wire the Settings modal (gear button + theme) (PR #36 on `feat/a1-settings-modal-and-theme`; gear button next to Disconnect, `useTheme()` hook toggles `.dark` on documentElement based on persisted theme + subscribes to `prefers-color-scheme` for `auto`, Tailwind v4 dark variant rebound via `@custom-variant` in `index.css`, shell surfaces (WorkspacePage outer/header/query bar, Layout, App LoadingFallback) repainted with `dark:` pairs; 11 new unit tests; deeper component repaint deferred to follow-up)
- [x] **A2** — Fix tab pin/unpin (PR #26 on `fix/tab-pin-unpin`; `onTabUnpin` wired through, pin button conditionally rendered as `tab.pinned ? onTabUnpin : onTabPin` so a parent supplying only one direction no longer renders a no-op button)
- [x] **A3** — Add Pin / Hide actions in NodeContextMenu (PR on `feat/a3-a5-pin-hide-and-viz-limits`; bundled with A5. `NodeContextMenu` props extended with `onPin?` / `onHide?` plus `isPinned` / `isHidden`; menu now renders Expand → Pin/Unpin → Hide/Show → Delete with state-aware labels and `aria-pressed`; pinned nodes get a distinct amber stroke (`#f59e0b`, width 3) on the canvas; `ResultTab` reads pin/hide state from `useGraphStore`. 8 unit tests added.)
- [x] **A4** — Remove the debug marker (or gate it on env) (PR #25 on `fix/graphview-debug-marker`; gated on `import.meta.env.DEV` with Vite ambient types added in `frontend/src/vite-env.d.ts`)
- [x] **A5** — Enforce viz limits in WorkspacePage before rendering (PR on `feat/a3-a5-pin-hide-and-viz-limits`; bundled with A3. `WorkspacePage` reads `maxNodesForGraph` / `maxEdgesForGraph` from `settingsStore`, computes a single `vizDisabledReason`, force-flips `viewMode` to `table` via `useEffect`, and feeds the same string to `ResultTab`. The existing `result.visualization_warning` plumbing was generalised into a unified `vizUnavailableReason` (server warning takes precedence). Banner now exposes an "Open Settings" action when the reason is client-side. 5 unit tests added.)
- [x] **A6** — Unify the label color palette (PR on `fix/unify-color-palette`; `graphStyles.getDefaultNodeColor` now delegates to `nodeColors.getNodeLabelColor`, dropping the duplicate `d3.scaleOrdinal` insertion-order map; sidebar pill and graph circle share one map and resolve to the same hex for the same label regardless of render order; new `graphStyles.test.ts` pins the contract with 7 regression tests; dead `scaleOrdinal`/`schemeCategory10` mocks pruned from `GraphView.test.tsx`)
- [x] **A7** — Fix `expand_node` for `depth != 1` (PR #27 on `fix/expand-node-depth`; depth-2 now returns intermediate nodes via `nodes(path)`)
- [x] **A8** — Make the per-user rate limit actually fire (PR #29 on `fix/per-user-rate-limit`; resolves user via `session_manager.get_user_id` so the cookie can't drift from the manager)
- [x] **A9** — Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example` (PR #30 on `chore/license-changelog-env`; Apache-2.0 LICENSE + matching NOTICE, Keep-a-Changelog-style CHANGELOG seeded with 0.1.0, full env example covering every `Settings` key + `ADMIN_PASSWORD` with required-in-prod markers; verified that `cp backend/.env.example backend/.env` boots cleanly. Caught a doc/code drift along the way: pydantic-settings parses `List[str]` as JSON, so `CORS_ORIGINS` must be a JSON array even though `docs/CONFIGURATION.md` shows the comma form — recorded as follow-up)
- [x] **A10** — Surface JSON parameter parse errors instead of silently dropping them (PR #31 on `fix/query-params-error-surface`; `getQueryParams` now returns `{ ok, value } | { ok, error }`, the editor renders an inline `role="alert"` caption + red border under the params textarea, disables Execute with a tooltip, blocks Shift+Enter, and shows a red dot on the `Parameters` toggle when the panel is collapsed; 12 unit tests added)
- [x] **A11** — Add additive double-click expand (with reversible "isolate" mode)
  - [x] Phase 1 — additive double-click via shared `mergeGraphElements` (PR #23, commits `461b202`, `dc11d06` on `main`)
  - [x] Phase 2 — camera focus animation on newly-added neighbourhood (PR #35 on `feat/a11-camera-focus-and-isolate`, bundled with phase 3; `graphStore.cameraFocusAnchorIds` set after merge, GraphView animates `d3.zoomIdentity` over 400ms to the anchor union and briefly pins the clicked node for 2s)
  - [x] Phase 3 — explicit reversible "isolate" context-menu action with `← Back to full result` breadcrumb (PR #35 on `feat/a11-camera-focus-and-isolate`, bundled with phase 2; `queryStore.isolateNeighborhood` snapshots into `previousGraphElements` and filters to incident edges, `restoreGraphElements` round-trips the snapshot, `ResultTab` renders the breadcrumb when both snapshot + handler are present)

### Milestone B — CI and production deployment are real

- [x] **B1** — GitHub Actions: `backend-ci.yml` (PR #37 + follow-ups; lint=ruff/black/mypy, unit, integration)
  - [x] **B1.1** — enable `black --check .` in the lint job (PR #40 on `feat/b1.1-b8-black-and-precommit`, bundled with B8; ran `black app tests` across the backend tree using existing `[tool.black]` config — 67 files reformatted, net −49 lines, zero behavioural deltas, isolated in a single `style(backend): ...` commit for `--ignore-revs` friendliness; `black --check .` step in `backend-ci.yml` now uncommented and green)
  - [x] **B1.2** — enable `mypy app` in the lint job (PR on `feat/b1.2-mypy-ci`; metrics faux type-comment fix; typing fixes across app; `warn_return_any` relaxed with comment — see ticket body under Milestone B §B1)
  - [x] **B1.3** — integration job with `apache/age:dev_snapshot_PG16` service + `USE_REAL_TEST_DB=true` + `alembic upgrade head` before `pytest -m integration --no-cov` (PR on `feat/b1.3-integration-ci`; `connected_client` real path fixed to single pool via `/session/connect` + `/disconnect`; `_integration_db_config()` shared with `test_db_config`; `_configure_age` ends with `commit` so psycopg_pool stops discarding connections; `test_database_connection` uses `_pool` + `transaction()` API)
- [x] **B2** — GitHub Actions: `frontend-ci.yml` (PR #37, bundled with B1; eslint/typecheck/vitest/vite-build all wired, pre-existing tsc + eslint debt cleared so the gate is green on day one)
- [x] **B3** — GitHub Actions: `container.yml` (PR #38 on `feat/b3-b4-b5-container-images`, bundled with B4+B5; matrix build over `{backend, frontend}`, tag-triggered push to Docker Hub as `<namespace>/kotte-{backend,frontend}` + `workflow_dispatch` with explicit `image_tag`/`push_latest` inputs + PR-triggered build-only, Trivy v0.35.0 `HIGH,CRITICAL` gate with `ignore-unfixed`, GHA-backed layer cache per image, third-party actions SHA-pinned matching the `viper` repo's conventions)
- [x] **B4** — Multi-stage backend image (PR #38, bundled with B3+B5; two-stage `python:3.11-slim` with `pip install --target=/install` in stage 1 and `libpq5` + `curl` + non-root `kotte` user + curl-based `HEALTHCHECK` in stage 2; validated locally, ~400 MB runtime)
- [x] **B5** — Multi-stage frontend image (production) (PR #38, bundled with B3+B4; new `deployment/frontend.Dockerfile.prod` + `deployment/nginx.conf`; `node:20-alpine` builder → `nginx:alpine` runtime ~64 MB; SPA fallback + gzip + immutable asset caching + no-cache on index.html + static-hardening headers; dev `frontend.Dockerfile` left untouched for compose)
- [x] **B6** — Compose split (dev / prod) (PR #39 on `feat/b6-compose-split`; legacy `docker-compose.yml` removed, replaced with `docker-compose.dev.yml` (source mounts + `uvicorn --reload` + vite HMR via anonymous-volume trick) and `docker-compose.prod.yml` (nginx SPA via `frontend.Dockerfile.prod`, `restart: unless-stopped`, per-service `mem_limit`/`cpus`, `read_only` nginx with tmpfs, `env_file` secrets, no source mounts, age not exposed on host); `deployment/.env.prod.example` documents the four required secrets; six Makefile targets wrap both stacks)
- [x] **B7** — Migrations system (Alembic) (PR #41 on `feat/b7-alembic-migrations`; `backend/alembic/` scaffolded with URL resolution from DB_* env vars / `ALEMBIC_SQLALCHEMY_URL` / `-x url=...`, `target_metadata=None` because there's no ORM, raw-SQL migrations only; two shipped revisions — `2c3c565210b1` enable-age-extension + `78c03fa27fda` create-kotte_users-stub; label-index creation deliberately kept as `scripts/migrate_add_indices.py` → `make reindex-labels` because it depends on runtime catalog state; `docs/MIGRATIONS.md` is the operator guide; Makefile grows six migration targets; validated end-to-end against a fresh AGE container including downgrade + idempotency)
- [x] **B8** — Pre-commit (PR #40 on `feat/b1.1-b8-black-and-precommit`, bundled with B1.1; `.pre-commit-config.yaml` at repo root with black 26.3.1, ruff v0.15.11, eight generic hygiene hooks from pre-commit-hooks v6.0.0, and a local frontend-eslint hook reusing the installed plugin set; Python language version deliberately un-pinned so 3.10/3.12/3.13 distros can install hooks; `pre-commit>=3.5.0` added to `requirements-dev.txt` + `pyproject.toml` dev extra; new Makefile targets `install-hooks` / `precommit-run` / `format-backend`; hygiene auto-fixes on first run: 9 trailing-whitespace + 28 EOF-newline files; incidental cleanup: `git rm --cached frontend/test-results/.last-run.json` + `.gitignore` entries for `frontend/test-results/` and `frontend/playwright-report/`)
- [x] **B9** — Doc reconciliation pass (PR on `docs/sync-post-a10`; QUICKSTART "Next Steps" rewritten, ARCHITECTURE pointer fixed off the non-existent `app/core/security.py` and onto `middleware.py` / `auth.py` / `credentials.py` / `validation.py`, CONFIGURATION drops the unimplemented `sqlite`/`postgresql`/`redis` credential backends and corrects `CORS_ORIGINS` to the JSON-array form `pydantic-settings` actually accepts, KUBERNETES_DEPLOYMENT now flagged "planned, not shipped." REVIEW.md strikethrough-updated for A2/A4/A10. One follow-up code change tracked separately: `Settings.cors_origins` validator that accepts both comma-separated and JSON-array forms.)

### Milestone C — Make it a graph product

- [x] **C1** — CodeMirror 6 Cypher editor (Neo4j mode + graph-catalog schema completion — see C1 section)
- [ ] **C2** — Visualization upgrades — **C2.1–C2.3 shipped** (directed arrows, curved multi-edges, self-loops in `GraphView` + `graphLinkPaths.ts`); **C2.4–C2.6** pending (canvas/Pixi, minimap, lasso); see §C2 above
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
