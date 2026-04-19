# Changelog

All notable changes to **Kotte** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Status:** Pre-1.0. Public API and data shapes may still change between
> minor versions. Breaking changes will be called out under **Changed** with
> a migration note.

## [Unreleased]

### Added
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
