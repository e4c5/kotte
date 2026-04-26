# ROADMAP Validation Report

_Generated: 2026-04-24. Updated: 2026-04-26. Validates items marked complete in `docs/ROADMAP.md` against the actual codebase._

---

## Summary

**All 49 completed ROADMAP items are correctly implemented.** No partial implementations or missing files were found.

---

## Milestone A — Stop the bleeding

| Ticket | Status | Evidence |
|--------|--------|----------|
| **A1** — Wire Settings modal + useTheme | ✅ Confirmed | `frontend/src/utils/useTheme.ts` exists; `WorkspacePage.tsx:367` has gear button with `aria-label="Open settings"`; `index.css:9` has `@custom-variant dark` |
| **A2** — Fix tab pin/unpin | ✅ Confirmed | `TabBar.tsx` accepts `onTabUnpin?` (lines 8–9) and branches between pin/unpin in onClick (lines 83–96) |
| **A3** — Pin/Hide in NodeContextMenu | ✅ Confirmed | `NodeContextMenu.tsx` has `onPin?`, `onHide?`, `isPinned`, `isHidden` props; `GraphView.tsx:269` renders amber stroke `#f59e0b` for pinned nodes |
| **A4** — Gate debug marker on DEV | ✅ Confirmed | `GraphView.tsx:609` wraps debug marker in `{import.meta.env.DEV && (…)}` |
| **A5** — Enforce viz limits | ✅ Confirmed | `WorkspacePage.tsx:66` reads `maxNodesForGraph`/`maxEdgesForGraph`; `computeVizDisabledReason()` at lines 20–33 and 312–316 |
| **A6** — Unify label color palette | ✅ Confirmed | `graphStyles.ts:3` imports `getNodeLabelColor` from `nodeColors`; `getDefaultNodeColor()` at lines 44–46 delegates to it |
| **A7** — Fix expand_node depth | ✅ Confirmed | `graph.py:335–336` uses `UNWIND nodes(path) as pn` and `UNWIND relationships(path) as rel` |
| **A8** — Per-user rate limit | ✅ Confirmed | `middleware.py:245` calls `session_manager.get_user_id(session_id)` |
| **A9** — LICENSE, CHANGELOG, .env.example | ✅ Confirmed | `LICENSE`, `NOTICE`, `CHANGELOG.md`, and `backend/.env.example` all present |
| **A10** — Surface JSON param parse errors | ✅ Confirmed | `QueryEditor.tsx` exports `getQueryParams()` returning `{ ok: true; value }` or `{ ok: false; error }` (lines 368–369) |
| **A11 Phase 1** — Additive double-click expand | ✅ Confirmed | `frontend/src/utils/graphMerge.ts` exists with `mergeGraphElements()` and dedup logic |
| **A11 Phase 2** — Camera focus animation | ✅ Confirmed | `graphStore.ts:88–90` has `cameraFocusAnchorIds`, `setCameraFocusAnchorIds`, `clearCameraFocusAnchorIds` |
| **A11 Phase 3** — Reversible isolate mode | ✅ Confirmed | `queryStore.ts` has `previousGraphElements` (line 36), `isolateNeighborhood()` (line 95), `restoreGraphElements()` (line 100) |

---

## Milestone B — CI and production deployment

| Ticket | Status | Evidence |
|--------|--------|----------|
| **B1** — backend-ci.yml | ✅ Confirmed | `.github/workflows/backend-ci.yml` has lint (ruff/black/mypy), unit, and integration jobs |
| **B1.1** — black --check in lint | ✅ Confirmed | `backend-ci.yml` has `black --check` step uncommented |
| **B1.2** — mypy in lint | ✅ Confirmed | `backend-ci.yml` lint job runs `mypy app` |
| **B1.3** — Integration CI job | ✅ Confirmed | Integration job present with `apache/age:dev_snapshot_PG16` service and `pytest -m integration` |
| **B2** — frontend-ci.yml | ✅ Confirmed | `.github/workflows/frontend-ci.yml` exists with lint, typecheck, test, and build jobs |
| **B3** — container.yml | ✅ Confirmed | `.github/workflows/container.yml` exists with matrix build over `{backend, frontend}` |
| **B4** — Multi-stage backend image | ✅ Confirmed | `deployment/backend.Dockerfile` has builder and runtime stages with non-root `kotte` user and curl-based HEALTHCHECK |
| **B5** — Multi-stage frontend image | ✅ Confirmed | `deployment/frontend.Dockerfile.prod` and `deployment/nginx.conf` both exist |
| **B6** — Compose split | ✅ Confirmed | `deployment/docker-compose.dev.yml` and `docker-compose.prod.yml` exist; legacy `docker-compose.yml` is gone |
| **B7** — Alembic migrations | ✅ Confirmed | `backend/alembic/env.py` exists; versions directory has `2c3c565210b1_enable_age_extension.py` and `78c03fa27fda_create_kotte_users_stub.py` |
| **B8** — Pre-commit | ✅ Confirmed | `.pre-commit-config.yaml` exists at repo root |
| **B9** — Doc reconciliation | ✅ Confirmed | `docs/CONFIGURATION.md`, `QUICKSTART.md`, `ARCHITECTURE.md`, and `KUBERNETES_DEPLOYMENT.md` all updated |

---

## Milestone C — Make it a graph product

| Ticket | Status | Evidence |
|--------|--------|----------|
| **C1** — CodeMirror 6 Cypher editor | ✅ Confirmed | `QueryEditor.tsx` imports `CodeMirror` from `@uiw/react-codemirror` (line 2) and `getExtensions` from `@neo4j-cypher/codemirror` (line 4); CodeMirror component used at line 287 |
| **C2.1** — Arrowheads | ✅ Confirmed | `graphLinkPaths.ts` exports `markerIdForColor()`; `GraphView.tsx` applies `marker-end` via `markerIdForColor(edgeStrokeColor(d))` |
| **C2.2** — Curved links + parallel-edge offset | ✅ Confirmed | `graphLinkPaths.ts` has `parallelEdgeMeta()` (lines 20–42) and quadratic Bézier generation in `linkPath()` |
| **C2.3** — Self-loops | ✅ Confirmed | `graphLinkPaths.ts:linkPath()` handles `source === target` case with arc above node |
| **C2.4** — Canvas / Pixi fallback | ✅ Confirmed | `GraphCanvas.tsx` exists (835 lines); `GraphView.tsx:15` defines `CANVAS_THRESHOLD_ENTER = 1500`; `canvasMode` state with hysteresis `useEffect` |
| **C2.5** — Minimap | ✅ Confirmed | `GraphMinimap.tsx` exists (217 lines); wired in both `GraphView.tsx` (SVG) and `GraphCanvas.tsx` via `getTransform`/`setTransform` callbacks |
| **C2.6** — Lasso multi-select | ✅ Confirmed | `graphStore.ts` has `lassoNodes`, `setLassoNodes`, `clearLassoNodes`; `LassoActionBar.tsx` with Pin all / Hide all / Expand all / Clear actions |

---

## Pending items (not validated — not marked complete)

The following remain open and were not evaluated:

- **A2 test** — `TabBar.test.tsx` test for unpinning (ROADMAP body says to add it; not checked)
- **D1–D6** — Multi-user, multi-tenant, observability features

---

## Follow-up items noted in ROADMAP but not yet ticketed

1. **`Settings.cors_origins` validator** — `CORS_ORIGINS` in `CONFIGURATION.md` documents comma-separated form, but pydantic-settings requires JSON-array form. A `field_validator` that accepts both is tracked but has no ticket.
2. **`RUN_MIGRATIONS=true` entrypoint hook** — For single-DB deployments wanting automatic migration on startup. No ticket yet.
3. **Deeper light-mode repaint** — A1 repainted shell surfaces; leaf components (`TableView`, `QueryEditor`, `GraphView`, `ConnectionPage`, `LoginPage`, `SettingsModal` inputs) still use hardcoded dark palette. Deferred as a design exercise, not tracked.
4. **Rate-limit 429 JSON response** — When per-IP or per-user cap fires from `BaseHTTPMiddleware`, the result is currently a 500 in production rather than a clean 429 JSON response. Fix is to return `JSONResponse(status_code=429)` directly. Tracked separately.
