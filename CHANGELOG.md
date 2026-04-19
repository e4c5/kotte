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
