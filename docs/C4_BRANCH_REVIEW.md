# C4 Branch Review

_Generated: 2026-04-26. Review of the `C4` branch against `main`, cross-referenced with `docs/ROADMAP.md` and `docs/ROADMAP_VALIDATION.md`._

---

## Branch overview

**Branch:** `C4` (4 commits ahead of `main`)
**Diff:** +3,606 / −411 across 33 files.

| SHA | Roadmap items | Summary |
|-----|---------------|---------|
| `44927e5` | C3–C7 | Streaming, schema sidebar 2.0, templates, safe mode, expand options |
| `c7168dd` | C2.4 | Canvas 2D renderer with threshold/hysteresis |
| `d23bac7` | C2.5 | GraphMinimap wired into SVG and Canvas renderers |
| `1ce7cf2` | C2.6 | Lasso multi-select (Shift+drag, bulk Pin/Hide/Expand actions) |

---

## Roadmap alignment

All 8 targeted items match their ROADMAP.md descriptions and acceptance criteria.

| Item | Description | Status |
|------|-------------|--------|
| **C2.4** | Canvas 2D fallback (`GraphCanvas.tsx`); `ENTER=1500 / EXIT=1350` hysteresis; `Path2D` edges, arrowheads, pan/zoom, click/dblclick/contextmenu, edge hit-test, camera focus, PNG export | ✅ Implemented |
| **C2.5** | `GraphMinimap.tsx` — DPR-aware secondary canvas (160×120), ~10 fps RAF loop, node dots via `getNodeLabelColor`, viewport rect, click-to-center / drag-to-pan; wired into both SVG and Canvas renderers | ✅ Implemented |
| **C2.6** | `Shift+drag` rectangular lasso → `lassoNodes: Set<string>` in `graphStore`; dashed-ring highlight in SVG and Canvas; `LassoActionBar.tsx` bulk-action strip (Pin all / Hide all / Expand all / Clear) | ✅ Implemented |
| **C3** | Server-side cursor streaming via `stream_cypher` on `DatabaseConnection`; NDJSON chunked response; `queryStore.streamQuery` with `AbortController`; `TableView` streaming indicator; cap + safe-mode guards | ✅ Implemented |
| **C4** | Schema sidebar 2.0 — collapsible `NodeLabelRow`/`EdgeLabelRow` with property chips, property type inference (`MetadataService.infer_property_types`), indexed-property badges (`MetadataService.get_indexed_properties`), Sample 5 / Match all actions, `LibraryPanel` | ✅ Implemented |
| **C5** | `LibraryPanel` in `MetadataSidebar.tsx`; `GET /queries/templates` via `queryAPI.listTemplates()`; template rows with "Use template" button; params pre-fill via `handleQueryTemplate(query, params?)` | ✅ Implemented |
| **C6** | `SET TRANSACTION READ ONLY` server-side enforcement in both `query.py` and `query_stream.py`; regex block removed; client-side `MUTATION_RE` detection + amber confirmation modal; `mutation_confirmed: bool` on `QueryExecuteRequest` | ✅ Implemented |
| **C7** | `ExpandOptionsPopover.tsx` — direction toggle, depth buttons, limit input, edge-label checkboxes, screen-edge collision detection; `NodeExpandRequest` extended with `edge_labels` + `direction`; `NodeExpandResponse` extended with `truncated` + `total_neighbours` (cheap count query); truncation badge in `ResultTab` | ✅ Implemented |

---

## Implementation checklist

### Blocking (must fix before merge)

- [x] **Fix `GraphView.test.tsx` d3 zoom mock** — C2.6 added `.filter()` to the d3 zoom chain (`GraphView.tsx:251`) and `.join()` for the lasso ring group, but the d3 mock did not include either method. Fixed by adding `filter: vi.fn().mockReturnThis()` to the zoom mock and `join: vi.fn().mockReturnValue(selection)` to the selection mock. 126/126 tests now pass.

### Recommended (non-blocking, should address before or shortly after merge)

- [x] **`LassoActionBar` "Expand all" concurrency guard** — `expandAll()` now runs sequentially (`for...of` with `await`), caps at `MAX_EXPAND_BATCH = 20` nodes, disables the button while expanding, and shows a tooltip warning when the selection exceeds the limit.

- [x] **`ROADMAP_VALIDATION.md` refresh** — Updated the Milestone C table to confirm C2.4, C2.5, and C2.6; moved them out of the "Pending items" section; bumped the summary count from 46 to 49.

- [ ] **`GraphCanvas.tsx` size** — At 835 lines this is the largest single component. If it grows further, consider extracting the draw loop and hit-testing logic into a `useCanvasRenderer` hook or separate module.

### Observations (no action required)

- **Label inlining in Cypher (backend)** — `MetadataService.infer_property_types` and `get_indexed_properties` interpolate `validated_label_name` via f-string into Cypher. This is safe because `validate_label_name` is called first, consistent with `discover_properties` and `graph.py`'s expand endpoint.

- **`stream_cypher` cursor naming** — Uses a server-side named cursor with `query_hash` for debuggability. `chunk_size` forwarded correctly to `fetchmany`.

- **Rate-limit 429 fix** — The middleware now returns `JSONResponse(429)` directly instead of raising `APIException`, resolving the known follow-up from A8 where `BaseHTTPMiddleware` swallowed the exception into a 500.

- **Expand endpoint concurrent queries** — `graph.py` fires the expand query and count query via `asyncio.gather` for latency optimisation. The `truncated` flag uses `len(nodes_list) >= limit`, which is approximate (fires when nodes equal the limit even if the total is exactly that). Intentional trade-off per ROADMAP.

- **`_infer_type` ordering** — `bool` is checked before `int`, which is correct since Python's `bool` is a subclass of `int`.

- **`_streamAbortControllers` outside persist** — Correct design: non-serialisable `AbortController` instances live outside Zustand's persist layer.

- **Mutation detection regex** — `MUTATION_RE = /\b(CREATE|DELETE|SET|REMOVE|MERGE|DETACH)\b/i` is a client-side hint only; the real enforcement is server-side via `SET TRANSACTION READ ONLY`. False positives (e.g. `SET` in property values) are acceptable since the user can confirm and proceed.

- **`MetadataSidebar` decomposition** — Refactored into `NodeLabelRow`/`EdgeLabelRow`/`LibraryPanel` sub-components. `asyncio.gather` runs property type inference + indexed property lookup concurrently with `discover_properties`, minimising metadata load latency.

---

## Test status

| Suite | Result | Notes |
|-------|--------|-------|
| **Frontend** | **126 passed** | Fixed: zoom mock now includes `.filter()` and selection mock includes `.join()` |
| **Backend** | Not runnable locally | Missing venv / `prometheus_client`; CI is authoritative |
