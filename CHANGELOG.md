# Changelog

All notable changes to **Kotte** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Status:** Pre-1.0. Public API and data shapes may still change between
> minor versions. Breaking changes will be called out under **Changed** with
> a migration note.

## [Unreleased]

### Added
- **Container images + Docker Hub publish pipeline (ROADMAP B3+B4+B5)** —
  production-oriented multi-stage Dockerfiles for both services and a
  GitHub Actions workflow that builds, scans, and publishes them.
  - `deployment/backend.Dockerfile` rewritten as two stages. Stage 1
    uses `python:3.11-slim` with `build-essential` + `libpq-dev` and
    `pip install --target=/install -r requirements.txt`; stage 2 is a
    fresh `python:3.11-slim` with only `libpq5` + `curl`, imports the
    pre-built tree via `COPY --from=builder /install /app/site-packages`
    (with `PYTHONPATH` + `PATH` set so the console scripts resolve),
    copies the backend source, creates a non-root `kotte` user with
    `/usr/sbin/nologin` shell, `USER kotte`, exposes 8000, and ships a
    `HEALTHCHECK CMD curl --fail --silent --show-error
    http://localhost:8000/api/v1/health`. Validated end-to-end locally
    (image builds, container boots, `/api/v1/health` returns
    `{"status":"healthy", ...}`). Final runtime image ~400 MB — build
    tools stay in the builder stage so CVEs there never reach
    production.
  - `deployment/frontend.Dockerfile.prod` (new) is also two stages.
    Stage 1 `node:20-alpine` runs `npm ci --no-audit --no-fund` +
    `npm run build`; stage 2 `nginx:alpine` drops the default server
    block, ships our `nginx.conf`, and copies only the `dist/` tree
    from the builder. Runtime image ~64 MB. Validated locally: SPA
    fallback (`/workspace/anything` → 200 + index.html), single
    `Cache-Control: public, max-age=31536000, immutable` header on
    hashed `/assets/*`, `no-cache, no-store, must-revalidate` on
    `/index.html`, and gzip active on JS/CSS responses. The dev
    `frontend.Dockerfile` is unchanged so `deployment/docker-compose.yml`
    continues to work for local development.
  - `deployment/nginx.conf` (new) carries the gzip rules (1 KB
    threshold, text/JS/CSS/JSON/wasm types), SPA fallback via
    `try_files`, asset cache-control (immutable for `/assets/`,
    no-cache for `/index.html`), `server_tokens off`, and static-
    response hardening headers (`X-Content-Type-Options: nosniff`,
    `X-Frame-Options: DENY`, `Referrer-Policy:
    strict-origin-when-cross-origin`).
  - `.github/workflows/container.yml` (new) drives the image pipeline
    for both services in a matrix, publishing to **Docker Hub** as
    `<namespace>/kotte-backend` and `<namespace>/kotte-frontend` (matches
    the Docker Hub conventions used by the rest of the author's
    projects — e.g. `viper` — for consistent pull paths across the
    portfolio). Triggers: tag pushes matching `v*` (build + Trivy scan
    + push), `workflow_dispatch` with explicit `image_tag` + optional
    `push_latest` inputs for on-demand backfills, and PRs that touch
    the Dockerfiles / nginx config / workflow / `requirements.txt` /
    `package-lock.json` (build + Trivy scan, no push, so Dockerfile
    regressions are caught before release). Uses buildx with
    GHA-backed layer cache (`cache-from: type=gha, scope=<image>`,
    `mode=max`), tags via `docker/metadata-action` (semver
    major.minor.patch + major.minor + short sha + latest on default
    branch + raw `image_tag`/`latest` on dispatch), and Trivy v0.35.0
    with `severity: HIGH,CRITICAL`, `exit-code: 1`,
    `ignore-unfixed: true`. `concurrency.cancel-in-progress` enabled.
    All third-party actions pinned to commit SHAs (checkout 4.2.2,
    setup-buildx 3.12.0, login 3.7.0, metadata 5.7.0, build-push
    6.19.2, trivy-action 0.35.0) for supply-chain hygiene; Docker Hub
    login gated on `github.event_name != 'pull_request'` so fork PRs
    don't try to auth with secrets they can't see. Required secrets:
    `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. Optional variable
    `DOCKERHUB_NAMESPACE` overrides the publish namespace (defaults to
    `DOCKERHUB_USERNAME`) for org accounts. On fork / secretless PRs
    the namespace resolve step falls back to a local-only `ci`
    placeholder so the build + Trivy scan path still runs (the image
    is never pushed in that case, so the placeholder tag is harmless).
- **GitHub Actions CI for backend and frontend (ROADMAP B1+B2)** —
  two new workflows guard the test and lint surface on every push to
  `main` and every PR.
  - `.github/workflows/backend-ci.yml` runs `ruff check .` and
    `pytest -m "not integration and not performance" --no-cov` (234
    tests) on Python 3.11 with pip cache. Black, mypy, and the
    integration job are deliberately deferred to follow-up tickets
    (B1.1/B1.2/B1.3) so the workflow is green from day one rather than
    gating on pre-existing debt — see roadmap notes for scope.
  - `.github/workflows/frontend-ci.yml` runs four parallel jobs on
    Node 20 with npm cache: `eslint` (strict, `--max-warnings 0`),
    `tsc --noEmit`, `vitest run` (119 tests), `vite build`.
  - Both workflows scope by path (`backend/**` / `frontend/**` plus the
    workflow file itself) and use `concurrency.cancel-in-progress` so
    superseded runs don't burn CI minutes.
  - Pre-existing test/lint debt cleared as part of the same PR so CI
    starts green: 38 ruff autofixes + 3 manual dead-variable deletions
    in `app/api/v1/auth.py`, `app/api/v1/session.py`,
    `app/core/validation.py`; 4 frontend tsc errors (`GraphView.tsx`
    `string|null` widening on `getEdgeStyle`/`getEdgeCaption`,
    `ResultTab.test.tsx` GraphNode literal completeness,
    `GraphView.test.tsx` unused `name`, `api.test.ts`
    `global` → `globalThis`); 3 eslint errors + 3 warnings via inline
    `// eslint-disable-next-line` directives with one-line
    justifications (each `any` site, two intentional mount-only
    effects, the `getQueryParams` co-location). Added
    `argsIgnorePattern: '^_'` and `varsIgnorePattern: '^_'` to the
    eslint config so `_`-prefixed unused args are accepted.
  - Restored the inner `from app.main import create_app` re-import in
    `backend/tests/integration/conftest.py` that ruff had removed; that
    re-import is intentional after the `sys.modules` eviction so the
    fixture picks up the test env vars instead of the stale top-level
    binding (which silently bypassed the CSRF/rate-limit overrides and
    failed 39 integration tests).
- **Functional Settings entry point + theme switching (ROADMAP A1)** —
  the `WorkspacePage` header now renders a gear button next to `Disconnect`
  (`aria-label="Open settings"`) so users have a discoverable way into
  `SettingsModal`. Previously the modal could only be reached from a buried
  banner inside the viz-limit warning, which most users never see. Wired the
  modal's existing theme select to actually apply: a new `useTheme()` hook in
  `frontend/src/utils/useTheme.ts` toggles a `dark` class on
  `document.documentElement` based on the persisted `settingsStore.theme`
  value, subscribing to `prefers-color-scheme` while in `auto` mode and
  cleaning up on unmount. Tailwind v4's `dark:` variant is rebound to the
  class via `@custom-variant dark (&:where(.dark, .dark *));` in
  `frontend/src/index.css`. Repainted the shell-level surfaces
  (`WorkspacePage` outer/header/query bar, `Layout` non-workspace shell,
  `App` LoadingFallback) with `dark:` pairs so theme changes take effect
  without reload. Adds 11 new unit tests
  (`useTheme.test.ts` + `SettingsModal.test.tsx`).
  *Scope note:* leaf components (`TableView`, `QueryEditor`, `GraphView`
  canvas, `GraphControls` panels, `ConnectionPage`, `LoginPage`,
  `SettingsModal`'s own inline-styled inputs) keep their existing dark
  palette; an end-to-end light-mode repaint is left as follow-up work
  because it's a per-component design exercise rather than a refactor.
- `LICENSE` (Apache-2.0) at the repo root, with a matching `NOTICE` for attribution.
- `CHANGELOG.md` (this file) seeded with the work shipped to date.
- `backend/.env.example` enumerating every key on `app.core.config.Settings`
  plus `ADMIN_PASSWORD`, with one-line comments and "required-in-prod" markers.
  This makes `cp backend/.env.example backend/.env` a real onboarding step
  rather than a broken doc reference (ROADMAP A9).
- `QueryEditor` now surfaces JSON parameter parse errors instead of silently
  coercing them to `{}` (ROADMAP A10). The exported helper
  `getQueryParams` now returns a discriminated union
  `{ ok: true; value } | { ok: false; error }`; the editor renders an
  inline `role="alert"` caption + red border under the params textarea,
  disables the Execute button with a tooltip, blocks Shift+Enter from
  firing the query, and shows a red dot on the `Parameters` toggle button
  when the panel is collapsed so the disabled state has a visible cause.
  Adds 12 unit tests covering the parser and the new UI wiring.

### Changed
- `WorkspacePage.handleExecute` now bails when params don't parse, instead
  of passing the previous `{}` fallback through to `executeQuery` (defensive
  follow-on from the A10 fix).
- **Unified the label colour palette (ROADMAP A6)** —
  `frontend/src/utils/graphStyles.ts` no longer instantiates its own
  `d3.scaleOrdinal(d3.schemeCategory10)`; `getDefaultNodeColor` is now a
  thin delegating wrapper around `nodeColors.getNodeLabelColor`. The
  metadata-sidebar pill and the graph-canvas circle now share one
  module-level insertion-order map, so the same label resolves to the
  same hex regardless of which surface renders it first. Previously the
  two modules each had their own counter and could disagree on a colour
  whenever labels were encountered in different orders. Dropped the now-
  unused `d3` import from `graphStyles.ts`. Added
  `frontend/src/utils/graphStyles.test.ts` with 7 regression tests
  covering parity, both call orders, hex shape, distinctness, and that
  user-supplied `nodeStyles` overrides still win. Pruned the dead
  `scaleOrdinal`/`schemeCategory10` mocks from `GraphView.test.tsx`.
- **Doc reconciliation pass (ROADMAP B9)** — closes the four bullets B9
  enumerated, plus a few neighbours that drifted in the same direction:
  - `docs/QUICKSTART.md` "Next Steps" rewritten — the old list claimed D3
    visualisation, the query editor, CSV import, and graph interactions
    were still to be implemented; all of those have shipped. New copy is
    user-facing (run a query, expand a node, browse metadata, export
    results) with pointers to the User Guide and ROADMAP.
  - `docs/ARCHITECTURE.md` no longer points at `app/core/security.py`
    (which has never existed); the security section now correctly
    describes the actual split across `app/core/middleware.py`,
    `app/core/auth.py`, `app/core/credentials.py`, and
    `app/core/validation.py`.
  - `docs/CONFIGURATION.md` `CREDENTIAL_STORAGE_TYPE` row no longer
    advertises `sqlite` / `postgresql` / `redis` backends — only
    `json_file` is wired in `app/core/connection_storage.py`; the others
    are tracked under Milestone D.
  - `docs/CONFIGURATION.md` `CORS_ORIGINS` row corrected to the JSON-array
    form `pydantic-settings` actually accepts; comma-separated values
    fail at startup. A `Settings.cors_origins` validator that accepts
    both shapes is recorded as a follow-up.
  - `docs/KUBERNETES_DEPLOYMENT.md` now opens with a "planned, not
    shipped" banner — there are no manifests, no Helm chart, and no
    PostgreSQL-backed session/credential stores in the repo today; the
    document is design intent, not a deployment recipe.
  - `docs/REVIEW.md` G1, G2, §3 Milestone A items 2/4, and §4 item 3
    updated with strikethroughs + ✅ done annotations for the work that
    has shipped (A2, A4, A7, A8, A9, A10).
  - `docs/ROADMAP.md` "Suggested execution order" got a status note
    pointing at the progress checklist as the authoritative source; B9
    itself is marked done with a description of what shipped.
- **Pin / Hide actions surfaced in the node context menu (ROADMAP A3)** —
  `togglePinNode` / `toggleHideNode` already existed in `graphStore` and
  the force simulation already honoured `pinnedNodes` / `hiddenNodes`,
  but the menu was the missing UI surface. Right-clicking a node now
  exposes Pin/Unpin and Hide/Show entries (label flips on the current
  state, `aria-pressed` reflects it). Pinned nodes get a distinct amber
  stroke (`#f59e0b`, width 3) on the canvas so the indicator is visible
  even while the simulation re-settles. `NodeContextMenu` props extended
  with `onPin?`, `onHide?`, `isPinned`, `isHidden`; `ResultTab` reads the
  state from `useGraphStore` and wires the toggles. Adds 8 unit tests
  covering label flipping, conditional rendering, ordering, and handler
  wiring.
- **Camera focus on newly-added neighbourhood (ROADMAP A11 phase 2)** —
  double-clicking a node previously merged the new neighbours additively
  (phase 1) but then the canvas just re-fit to the *whole* expanded graph,
  which felt like the focus had been "lost" on a large result. Phase 2
  consumes the `addedNodeIds` already returned by `queryStore.mergeGraphElements`:
  `WorkspacePage.handleDoubleClickNode` now sets
  `graphStore.cameraFocusAnchorIds = [clickedNodeId, ...addedNodeIds]` after
  the merge, and `GraphView` watches that field. When non-empty, GraphView
  defers one animation frame (so the simulation has seeded positions for the
  new nodes), computes the bounding box of the anchor union, animates the
  d3-zoom transform with `transition().duration(400)` to that box (clamped
  to scale ∈ [0.3, 2.0] so single-node anchors don't max out the zoom),
  briefly pins the clicked node for 2s with `fx`/`fy` so the simulation
  settles around it, and then clears the field so the effect doesn't
  re-fire on every tick. Honours an explicit `pinnedNodes` entry — the
  2-second auto-release won't unpin a node the user has separately pinned.
  Adds 6 unit tests for the new `graphStore` actions
  (`setCameraFocusAnchorIds`, `clearCameraFocusAnchorIds`, dedup, identity
  preservation on no-op clear).
- **Reversible "isolate neighbourhood" mode (ROADMAP A11 phase 3)** —
  the destructive "show only this node" gesture that the original
  double-click attempt got wrong now lives where it belongs: as an
  explicit menu action with a one-click undo. `NodeContextMenu` adds a
  `Show only this & its neighbourhood` entry (between Hide and Delete)
  wired to a new `onIsolateNeighborhood` prop. `queryStore` gains
  `isolateNeighborhood(tabId, nodeId)` which snapshots the current
  `tab.result.graph_elements` into a new `tab.previousGraphElements`
  field and rewrites the canvas to keep only the clicked node, its
  incident edges, and those edges' endpoints (deterministic client-side
  filter — no API call). The companion `restoreGraphElements(tabId)`
  copies the snapshot back and clears it. `ResultTab` renders a
  `← Back to full result` breadcrumb above the canvas while the
  snapshot is held; it also hides the Isolate menu entry while in
  isolate mode (re-isolating would clobber the snapshot). The snapshot
  is dropped on `persist` rehydrate, since it's a view of `result`
  which is already dropped. Adds 7 store tests (round-trip,
  no-incident-edges edge case, no-graph-elements edge case, double-
  isolate guard, restore no-op) plus 3 menu tests + 4 ResultTab
  breadcrumb tests.
- **Client-side viz limit enforced before rendering (ROADMAP A5)** —
  `settingsStore.maxNodesForGraph` / `maxEdgesForGraph` (default
  5000 / 10000) were never checked, so a 50k-node accidental query would
  freeze the canvas. `WorkspacePage` now computes a single
  `vizDisabledReason` from the active result counts, force-flips the tab
  to `viewMode='table'` via `useEffect`, and feeds the same string to
  `ResultTab`. The existing `result.visualization_warning` plumbing was
  generalised into a unified `vizUnavailableReason` (server warning
  takes precedence; either source disables the Graph button + renders
  the banner). Banner now carries an "Open Settings" action when the
  reason is client-side, so the user can immediately raise the limit.
  Adds 5 unit tests covering banner rendering, button-disable, the
  Open-Settings affordance, and the no-reason baseline.

## [0.1.0] - 2026-04-19

First tagged baseline of the post-review codebase. Captures the Milestone A
"stop the bleeding" work tracked in [`docs/ROADMAP.md`](docs/ROADMAP.md), plus
the holistic review documented in [`docs/REVIEW.md`](docs/REVIEW.md).

### Added
- **Holistic review and forward roadmap** — `docs/REVIEW.md` + `docs/ROADMAP.md`
  capturing structural gaps (G1–G14), prioritised milestones (A → E), and
  per-ticket execution notes (PR #23).
- **Additive double-click expand (ROADMAP A11 phase 1)** — double-clicking a
  node now merges its neighbourhood into the existing graph via the shared
  `mergeGraphElements` primitive, instead of replacing the result set
  (PR #23, commits `461b202`, `dc11d06`).

### Changed
- **`expand_node` now returns intermediate nodes for `depth > 1`
  (ROADMAP A7)** — the Cypher path was previously truncated, silently
  dropping intermediate hops. Switched to `nodes(path)` /
  `relationships(path)` so depth-2 expansions surface the full subgraph.
  Added a regression test that asserts the query shape and parameter
  passing (PR #27).
- **Tab pin/unpin now actually unpins (ROADMAP A2)** — `onTabUnpin` is now
  wired through and the pin button is conditionally rendered based on the
  specific action available (`tab.pinned ? onTabUnpin : onTabPin`), so a
  parent that only supplies one direction no longer renders a button that
  silently does nothing (PR #26).
- **`GraphView` debug marker is now gated on `import.meta.env.DEV`
  (ROADMAP A4)** — the leftover red marker no longer ships in production
  builds; added Vite ambient types via `frontend/src/vite-env.d.ts` so
  `import.meta.env.DEV` is properly typed (PR #25).
- **`stream_query_results` cap-warning tests now align with the
  probe-based truncation check** — production code probes for one extra
  row before emitting a `cap_reached` warning; the tests were stuck on
  the pre-probe shape and falsely failing. Added a no-cap-warning test
  for the exact-match boundary, and factored the boilerplate into a
  shared `_collect_stream_chunks` helper (PR #28).

### Fixed
- **Per-user rate limit now actually fires (ROADMAP A8)** —
  `RateLimitMiddleware` previously read `request.scope["session"]["user_id"]`,
  but the Starlette signed-cookie session only ever held `session_id` /
  `csrf_token`. The middleware now resolves the user via
  `session_manager.get_user_id(session_id)`, so `rate_limit_per_user`
  is a real knob and the cookie can no longer drift from the manager.
  Added 4 unit tests covering the cap firing, bucket independence,
  unknown-session dormancy, and anonymous traffic (PR #29).

### Security
- **PR-scoped Sonar findings on the new test file cleared** —
  `python:S1313` (hardcoded test IP), `python:S1186` (empty function),
  `python:S7503` (`async def` without `await`). All three are scoped
  to test code; production paths were unaffected (PR #29 follow-up
  commit `8c6bfc0`).

### Notes / known follow-ups
- When the per-IP or per-user rate limit fires, `APIException` raised
  from a `BaseHTTPMiddleware` doesn't reach FastAPI's
  `add_exception_handler`-registered handlers. The cap is now reachable
  (the original A8 bug), but the response surfaces as a 500 with
  `INTERNAL_ERROR` logged rather than a clean 429 JSON. Tracked in the
  ROADMAP A8 section as a separate follow-up.
- Milestone A is partially complete: A2, A4, A7, A8, and A11 phase 1 are
  shipped; A1, A3, A5, A6, A9, A10, and A11 phases 2–3 remain. See
  the progress checklist in `docs/ROADMAP.md`.

[Unreleased]: https://github.com/e4c5/kotte/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/e4c5/kotte/releases/tag/v0.1.0
