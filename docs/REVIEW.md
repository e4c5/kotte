# Kotte — Holistic Review & Proposed Improvements

_Review date: 2026-04-18 (amended 2026-04-19 with G11; G11 phase 1 merged to `main` via PR #23. Further amended 2026-04-19 with strikethroughs for A2/A4/A7/A8/A9/A10 as those tickets shipped in PRs `#25`, `#26`, `#27`, `#29`, `#30`, `#31`.)_

This document is a **holistic** review of the Kotte project (a web visualizer for Apache AGE), not a line-by-line code review. It frames where the product sits today, the structural gaps that matter, and a prioritized improvement plan. Pair this with `docs/ROADMAP.md` (the ticketed implementation plan derived from this review) and `docs/ARCHITECTURE.md` (system design).

---

## Table of contents

1. [Where Kotte sits today](#1-where-kotte-sits-today)
2. [The structural gaps](#2-the-structural-gaps)
3. [Proposed roadmap (4 milestones)](#3-proposed-roadmap-4-milestones)
4. [If you only do three things](#4-if-you-only-do-three-things)

---

## 1. Where Kotte sits today

| Dimension | Reality |
|---|---|
| **Product positioning** | A Cypher console + light D3 SVG explorer for Apache AGE. Closer in spirit to a "psql for AGE with a graph view" than to Neo4j Browser/Bloom. |
| **Backend** | Solid bones: per-session pool, parameterized `cypher()` invocation, agtype parser, structured errors, Prometheus metrics, JSON logs. The backlog (P0–P4) cleaned up real correctness issues. |
| **Frontend** | Vite + React + Zustand + Tailwind. Multi-tab editor, metadata sidebar, several layouts, PNG/SVG export hooks. Editor is a plain `<textarea>`. |
| **Ops** | Dev-grade docker-compose. No multi-stage images, no production frontend image, no CI for tests/lint, no migrations system, no Helm/K8s manifests despite a planning doc. |
| **Docs** | Voluminous and well structured, but several docs describe **planned** behavior as if shipped (credential backends, K8s, "Next Steps" in QUICKSTART). |

The product is feature-complete _as a v0.1_. Most of the "shortcomings" are not bugs — they are **product depth**, **production-readiness**, and **wiring gaps** between things that exist but aren't connected.

---

## 2. The structural gaps

These are the issues that change how to plan the next 1–2 quarters, not just bug-fix tickets.

### G1. The visualizer is the product but is its weakest layer

You're competing for mindshare against people who have used Neo4j Browser. `GraphView.tsx` is **SVG-only**, single force layout actually animated, no arrowheads, no curved/parallel edges, no self-loop rendering, no minimap, no LOD/canvas/WebGL fallback, and **no client-side enforcement** of `maxNodesForGraph` / `maxEdgesForGraph`. ~~A debug banner is permanently visible — search `GraphView.tsx` for `GraphView marker:` to find it (currently around line 358).~~ **Resolved (ROADMAP A4, PR #25):** the marker is now gated on `import.meta.env.DEV` so it never ships in production builds.

The store has `togglePinNode` / `toggleHideNode` but **no UI calls them** (Pin/Hide on canvas — still tracked as ROADMAP A3). ~~There is a tab pin button but it can never _unpin_ — `TabBar` doesn't accept the `onTabUnpin` prop the workspace passes.~~ **Resolved (ROADMAP A2, PR #26):** `TabBar.Props` now declares `onTabUnpin` and the pin button is conditionally rendered as `tab.pinned ? onTabUnpin : onTabPin`, so a parent supplying only one direction no longer renders a no-op button.

### G2. The query editor is a textarea

No Cypher highlighting, no autocomplete from discovered labels/properties, no error squiggles, no parameter inspector beyond a "paste JSON" textarea. ~~that **silently** falls back to `{}` on parse failure (`QueryEditor.tsx:208-214`).~~ **Param-error surfacing resolved (ROADMAP A10, PR #31):** `getQueryParams` now returns a `{ ok: true; value } | { ok: false; error }` discriminated union; the editor shows an inline `role="alert"` caption + red border under the params textarea, disables Execute (with tooltip + ARIA), blocks Shift+Enter, and renders a small red dot on the collapsed Parameters toggle so the disabled state has a visible cause. The deeper "textarea → real Cypher editor with highlighting / autocomplete" gap remains tracked under Milestone C. _(Note: a code-review bot also flagged that `JSON.parse` accepts arrays, primitives, and `null` — adding an object-shape guard in `getQueryParams` is captured as a follow-up on PR #31; not yet merged.)_ For a tool that markets itself on Cypher exploration, this is the second-biggest UX gap after G1.

### G3. Settings, theme, and many configurable behaviors are dead surface

`SettingsModal` is wired but **never opened** — `WorkspacePage` declares `useState(false)` and never flips it (`pages/WorkspacePage.tsx:48,425-429`). That means `theme`, `defaultViewMode`, `queryHistoryLimit`, `autoExecuteQuery`, `maxNodesForGraph`, `maxEdgesForGraph`, export format choice, and table page size are mostly inert. The workspace is hard-coded dark (`bg-zinc-950`) regardless of the theme setting. Two color systems for labels coexist — D3 `schemeCategory10` in graph view vs a fixed palette in `nodeColors.ts` — so the same label can be different colors in the sidebar pill and the graph circle.

### G4. "Streaming" is partly implemented but never used

`api/v1/query_stream.py` chunks NDJSON and even paginates with auto-injected `SKIP/LIMIT`, but if the user query already has LIMIT/SKIP it materialises the full window in memory then chunks (`query_stream.py:144-229`). The frontend `queryAPI.stream` exists, `TableView` accepts `streaming` / `onLoadMore` props, but **`ResultTab` never enables them**. So large-result UX is functionally identical to the non-streaming path. The streaming `fetch` also has no `AbortSignal`, so it cannot be cancelled cleanly from the UI.

### G5. The metadata service can punish large graphs

`MetadataService.get_graph_metadata` fans out `asyncio.gather` over **every** vlabel and elabel for property discovery (`api/v1/graph.py:123-179`). On a graph with many labels this becomes many concurrent `keys(n)` queries; with `db_pool_max_size=10` you saturate that user's pool before discovery completes. Property discovery is also Cypher `LIMIT 500` sampling (clamped from a default of 1000 — `services/metadata.py:66-75`), so reported properties are _probabilistic_, which is not surfaced in the UI.

### G6. Production deployment story is the biggest "advanced product / unprofessional ops" gap

- `deployment/frontend.Dockerfile` runs `npm run dev` (Vite dev server) (`frontend.Dockerfile:23-24`).
- `deployment/docker-compose.yml` sets `ENVIRONMENT: development` for the backend (line 37).
- No multi-stage builds.
- `docs/KUBERNETES_DEPLOYMENT.md` is a **plan**, not artifacts. No `deployment/k8s/`, no Helm chart.
- No migrations system. `init-db.sql` only runs `CREATE EXTENSION age`. The "indices migration" is a one-shot Python script.
- ~~No `LICENSE`, no `CHANGELOG`, no `backend/.env.example` (referenced by QUICKSTART)~~ — resolved in ROADMAP A9 (PR #30): Apache-2.0 `LICENSE` + `NOTICE`, Keep-a-Changelog `CHANGELOG.md` seeded with 0.1.0, and `backend/.env.example` enumerating every `Settings` key + `ADMIN_PASSWORD`. No `pre-commit` config yet (Milestone B).
- **`.github/workflows/` only contains `docs.yml`** — markdown lint, link check, spell check. There is **no CI for pytest, vitest, ruff/black/mypy/eslint, container builds, or security scans.** This is the single most urgent ops gap.

### G7. Multi-user is a façade

The data model imagines users (there's `services/user.py`, `api/v1/auth.py`, login flow), but in practice a single built-in `admin` from `ADMIN_PASSWORD` is the only path. There is no user CRUD route, no roles, no per-user resource quotas, no audit trail beyond log lines. The per-user rate limiter used to read `request.scope["session"]["user_id"]`, but the login flow stores `session_id` / `csrf_token` in that signed cookie session and not `user_id` — so per-user rate limiting was unreachable. **Resolved (ROADMAP A8, PR #29):** the middleware now resolves the user via `session_manager.get_user_id(session_id)`, so the cookie can never silently drift from `SessionManager`. (One follow-up remains: when the cap fires, `BaseHTTPMiddleware` raising `APIException` doesn't reach FastAPI's exception handlers, so the response currently surfaces as a 500 instead of a clean 429 JSON — tracked separately.)

Per-session pools amplify this: every connect builds an `AsyncConnectionPool` with `max_size=10`, so 50 concurrent users = **up to 500 PostgreSQL connections**, and stale sessions don't aggressively call `DatabaseConnection.disconnect()` on idle expiry — that is a real connection-leak risk in long-running processes.

### G8. AGE-specific correctness footguns

- `cypher_return_columns` infers RETURN arity by tokenizing user input. When it can't parse (unbalanced brackets, weird subqueries), it falls back to a single `result` column. AGE will **error** if real RETURN arity ≠ AS clause arity. The unit tests document the fallback but it's a real footgun.
- `agtype.py` is **JSON + regex normalization**, not a real agtype parser. It does heuristic key-quoting and `;`→`,` rewrites (`services/agtype.py:48-77`). Anything exotic — temporal types, geometry, certain numeric edge cases — is not first-class.
- ~~`expand_node` for `depth != 1` returns a `RETURN DISTINCT n, m, rel` where `n` is no longer in scope after `WITH DISTINCT path, m` — that path is **likely broken at runtime** (`api/v1/graph.py:339-346`).~~ **Resolved (ROADMAP A7, PR #27).** A re-read of the on-disk code showed the live query was `RETURN DISTINCT m, rel` (no scope error) — but it had a worse, quieter bug: depth-2 paths returned the endpoint and both relationships but **dropped the intermediate hop**, so the canvas drew floating edges. Fixed by switching to `WITH n, path`, then `UNWIND nodes(path)` + `UNWIND relationships(path)`, and `RETURN DISTINCT n, pn, rel`. Regression test in `backend/tests/integration/test_graph.py::test_expand_node_depth_two_returns_intermediate_nodes`.
- **Safe mode** is a regex over the uppercased query (`api/v1/query.py:124-136`) — comments and string literals containing `CREATE` will trip it; conversely, a clever cyrillic mix won't. It is not a parser-based read-only mode.
- The docs imply `cancel` is universal, but `query_stream.py` doesn't show the same registration with `query_tracker`, so streaming queries may not be cancellable.

### G9. Caching and invalidation are correct now but coarsely keyed

After P1.1 the backend cache uses prefix-based invalidation under a lock (good). The frontend cache invalidates **every** `/graphs` and `/queries` GET on **any** mutation (`services/api.ts:52-56`). That's safe but blunt: importing 10k rows nukes the metadata for every other graph in the same workspace.

### G10. Documentation drift

- `CONFIGURATION.md` claims `CREDENTIAL_STORAGE_TYPE` supports `sqlite`, `postgresql`, `redis` — only encrypted JSON file is implemented.
- `QUICKSTART.md` "Next Steps" still says things like _"Implement D3.js visualization"_ (line 119+).
- `ARCHITECTURE.md` references `app/core/security.py` but that file doesn't exist (concerns are split across `auth.py` / `middleware.py` / `credentials.py`).
- `KUBERNETES_DEPLOYMENT.md` reads as if it ships with the repo; it doesn't.

### G11. Double-click on a node was missing — and the first attempt to add it went the wrong way

Every comparable tool — Neo4j Browser, Apache AGE Viewer (Bitnine), Memgraph Lab, Linkurious, Bloom — treats the canvas as a **growing scratch space**: double-click _adds_ a node's first-hop neighbours to whatever is already on screen, preserving positions, pins, and prior expansions. Until very recently Kotte had no double-click affordance at all.

A first attempt to add one (on the now-discarded `double-click` branch) introduced a destructive `handleFocusNode` that wiped the canvas in two phases — first by filtering the existing `graph_elements` to only the clicked node's incident edges, then by replacing the entire result with the API expansion's nodes/edges. That code never landed on `main`. The lesson it leaves behind is worth recording, because it informs the design of the additive replacement:

- Wiping the user's prior context (query result, earlier expansions, drag positions, pin state) on every double-click is intolerable in a graph explorer — there is no undo, and re-running the original query will not restore positions.
- A two-phase rebuild creates a visible flicker (sparse "clicked node + visible neighbours" → API result, ~50–500 ms apart).
- A celebrity node with 5,000 neighbours silently shows 100 random ones when the `limit` cap is not surfaced.
- An untyped, undirected expansion (`(n)-[rel]-(m)`) gives the user no control over relationship type or direction.
- A `useRef` for camera focus that lives outside React's reactive flow makes the camera land in the wrong place on rebuilds.

The correct primitive already existed: `handleExpandNode` (the right-click "Expand neighborhood" handler) uses `mergeGraphElements` on `queryStore` and is purely additive. The right move was to make double-click reuse that flow, not to duplicate its data-fetch path with destructive semantics.

**Status (2026-04-19, merged to `main` via PR #23):** Phase 1 of the additive design has shipped.

- A pure helper `frontend/src/utils/graphMerge.ts` now owns the merge contract (node dedup by id, edge dedup by `(source, target, label)`, no input mutation, returns the ids of newly-added elements).
- `queryStore.mergeGraphElements` delegates to that helper, fixing a pre-existing edge-dedup bug that was silently producing duplicate links every time the right-click expand path was used.
- `GraphView` exposes `onNodeDoubleClick`; `ResultTab` and `WorkspacePage` wire it to the same flow as the right-click expand. Double-click is now additive from day one.
- `d3-zoom`'s default dblclick-to-zoom is suppressed on nodes via `event.stopPropagation()`.

Phases 2 and 3 (camera focus animation, and an explicit reversible "isolate" mode in the context menu) are tracked as separate PRs against `main` — see ROADMAP §A11.

---

## 3. Proposed roadmap (4 milestones)

Group the improvements into four chunks. Each milestone is roughly 2–4 weeks of focused work for one engineer.

### Milestone A — "Stop the bleeding" (1–2 weeks)

Cheap, high-value fixes that close the gap between _what's wired_ and _what users see_.

1. **Wire the Settings modal** — add a gear button in `Layout` / `WorkspacePage` and consume `theme`, `defaultViewMode`, `queryHistoryLimit`, `autoExecuteQuery`, viz limits, table page size, default layout, export format.
2. **Fix tab pin/unpin** — done in ROADMAP A2 (PR #26): `TabBar.Props` now accepts `onTabUnpin`; the pin button picks `tab.pinned ? onTabUnpin : onTabPin` so a parent passing only one direction no longer renders a no-op button.
3. **Add Pin / Hide UI** for nodes — extend `NodeContextMenu` to call `togglePinNode` / `toggleHideNode` already in the store.
4. **Remove the debug marker** from `GraphView` — done in ROADMAP A4 (PR #25): the `GraphView marker:` overlay is now gated on `import.meta.env.DEV` (with Vite ambient types added in `frontend/src/vite-env.d.ts`), so production builds never render it.
5. **Enforce `maxNodesForGraph` / `maxEdgesForGraph` in `WorkspacePage`** before passing data into `GraphView`; fall back to `TableView` with a banner.
6. **Unify color palette** — make `nodeColors` and `graphStyles` share one source of truth so sidebar pills match graph circles.
7. **Fix `expand_node` for `depth != 1`** (`api/v1/graph.py:339`) — done in ROADMAP A7 (PR #27): the real bug was missing intermediate nodes, not the originally-flagged scope error; switched to `nodes(path)` so depth-2 expansions are no longer truncated.
8. **Fix per-user rate limit** — done in ROADMAP A8 (PR #29): `RateLimitMiddleware` now resolves the user via `session_manager.get_user_id(session_id)` instead of reading a non-existent `user_id` off the cookie session. Per-user 429 is reachable; `rate_limit_per_user` is a real knob.
9. **Add `LICENSE`, `CHANGELOG.md`, `backend/.env.example`** — done in ROADMAP A9 (PR #30): Apache-2.0 `LICENSE` + `NOTICE`, Keep-a-Changelog `CHANGELOG.md` seeded with 0.1.0, full `backend/.env.example` covering every `Settings` key + `ADMIN_PASSWORD`. Verified `cp backend/.env.example backend/.env` boots cleanly. Caught a `CORS_ORIGINS` doc/code drift along the way (env requires JSON-array form, not the comma-separated form `CONFIGURATION.md` shows) — recorded as a follow-up.
10. **Add additive double-click expand** (G11) — wire the double-click handler to the existing `mergeGraphElements` primitive (✅ shipped via PR #23 to `main`); animate camera focus on the newly-added neighbourhood (ROADMAP A11 Phase 2); add an explicit reversible "show only this & neighbourhood" context-menu action with a one-step undo (ROADMAP A11 Phase 3).

### Milestone B — "CI and production deployment are real" (2–3 weeks)

The biggest credibility gap. None of these need product changes.

1. **GitHub Actions** — add workflows for `pytest` (with a postgres+age service container for integration tests gated on a label/branch), `vitest run`, `ruff/black/mypy`, `eslint`, frontend production build, and a SAST/dependency scan (e.g. `pip-audit` + `npm audit` + `trivy` on built images).
2. **Multi-stage Dockerfiles** — backend: builder + slim runtime, non-root, healthcheck. Frontend: `node:alpine` builder → `nginx:alpine` serving `dist/` with SPA fallback and gzip/brotli.
3. **Compose split** — `docker-compose.dev.yml` (current behavior) and `docker-compose.prod.yml` (nginx frontend, `ENVIRONMENT=production`, secrets from env-file, restart policies, resource limits, no source mounts).
4. **Migrations** — adopt Alembic for any backend-managed schema (sessions table when you move off in-memory, future user table) and ship `init-db.sql` upgrades through a versioned bootstrap script. Convert `migrate_add_indices.py` into a migration.
5. **K8s manifests or a Helm chart** — at minimum a working Deployment + Service + Ingress for backend and a Deployment + Service for nginx-frontend. Then either build the CloudNativePG path or remove `KUBERNETES_DEPLOYMENT.md` until you do.
6. **Pre-commit** — `ruff --fix`, `black`, `prettier` on changed files; reuse the cspell config for commit messages.
7. **Reconcile docs** — drop unimplemented credential backends from `CONFIGURATION.md`, update `QUICKSTART.md` "Next Steps", correct the security file path in `ARCHITECTURE.md`.

### Milestone C — "Make it a graph product, not just a console" (3–4 weeks)

What moves Kotte from "feature complete v0.1" to something a user would prefer over `psql` + Cytoscape.

1. **Replace the textarea with CodeMirror 6** + a Cypher mode. Add **schema-aware autocomplete** by feeding it the metadata sidebar's labels/properties. Show JSON-parameter validation errors instead of swallowing them.
2. **Visualization upgrades** in `GraphView`:
   - **Arrowheads**, **curved edges** for parallel edges, and **self-loop** rendering.
   - **Canvas / WebGL renderer** (e.g. PixiJS or Sigma.js) selected when nodes > ~1500. Keep SVG for ≤1500.
   - **Minimap** + **fit-to-selection**.
   - **Node sizing by property** (mirrors edge width which already exists).
   - **Lasso / box multi-select** + bulk actions (hide, pin, expand).
   - **Edge bundling** or **incremental layout** (foreground new neighbors when expanding) instead of restarting the simulation.
3. **Wire streaming end-to-end** — `ResultTab` opts into `queryAPI.stream` for large results, `TableView` virtualises rows, both expose `AbortController` to cancel from the UI. Server-side, switch to a real PostgreSQL named cursor inside `query_stream.py` instead of materialising the LIMIT/SKIP window.
4. **Schema sidebar 2.0** — show per-label property lists (the API already returns them but the UI hides them — `MetadataSidebar.tsx:133-173`), property types, indexed flag, sample values; allow drag-to-canvas.
5. **Saved queries / templates UI** — `services/query_templates.py` already exists on the backend; surface it as a library panel with parameter forms.
6. **Read-only mode that's actually safe** — replace the regex safe-mode with a Cypher AST parser (e.g. a lightweight grammar) or a server-side `SET TRANSACTION READ ONLY` plus a _separate_ mutating endpoint behind explicit confirmation.
7. **Expand options popover + truncation indicator** (depends on the Milestone A double-click fix) — extend the expand endpoint with edge-type, direction, and limit options; surface a "100 of 1,247" badge on truncated expansions.

### Milestone D — "Multi-user, multi-tenant, observable" (4+ weeks, optional but strategic)

Only if you intend Kotte to be deployed beyond a single analyst.

1. **Real user model** — DB-backed users (Alembic migration), bcrypt + optional OIDC/OAuth, roles (admin/editor/viewer), per-user saved-connection ACLs.
2. **Move sessions out of process memory** — Redis-backed `SessionManager` and `query_tracker`. This unblocks horizontal scaling and resolves the "cookie session sees 401 but pool may linger" leak.
3. **Per-tenant pool budgeting** — instead of `min=1, max=10` per session, a **shared** pool per `(user, host, database)` tuple with a global cap. Sessions reuse the pool; idle pools are reaped on a timer with explicit `disconnect()`.
4. **OpenTelemetry** — add tracing on the FastAPI middleware, propagate trace IDs into `request_id`, and instrument psycopg. Prometheus metrics are a good base; tracing is the missing dimension when you need to debug a slow query.
5. **Audit log** — first-class table (or append-only file) for connect/disconnect, query execute, mutation events, with user, IP, request ID. The current `SECURITY:` log prefix is informal.
6. **Rate-limit and idempotency for `csv_importer`** — currently reads the whole file into memory, splits by `,` (no RFC-4180 quoting), and embeds JSON property payloads directly into Cypher strings (`api/v1/csv_importer.py:206-214`). Move to streamed parsing (`csv` module or `pandas.read_csv`), parameterized inserts, and `COPY ... FROM` into a staging table for large files. Add idempotency keys so re-runs don't double-load.

---

## 4. If you only do three things

1. **CI + production-grade Docker images + LICENSE/CHANGELOG (Milestone B core).** Without this the project doesn't look maintained, no matter how good the code is.
2. **CodeMirror Cypher editor + schema-aware autocomplete + canvas renderer for >1500 nodes.** These two changes do more for perceived quality than anything else.
3. **Wire the existing settings, finish the rest of the Milestone A wiring fixes, and reconcile the docs.** ~~Pin/unpin~~ (A2), ~~`expand_node` depth-2~~ (A7), ~~per-user rate limit~~ (A8), ~~debug marker~~ (A4), ~~JSON-param error surfacing~~ (A10), and ~~LICENSE / CHANGELOG / `.env.example`~~ (A9) are all shipped or in flight; the still-open Milestone A diffs are the Settings modal wiring (A1), Pin / Hide UI on the canvas (A3), the viz-limit guard (A5), and the colour-palette unification (A6). Tiny diffs that close the gap between "what we built" and "what the user can find."
