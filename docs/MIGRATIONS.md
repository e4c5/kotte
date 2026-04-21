# Kotte database migrations

_Added in ROADMAP B7 (PR #41)._

Kotte ships an [Alembic](https://alembic.sqlalchemy.org/) migration
chain for bootstrapping and evolving schema in the target Apache AGE
database. This document explains what the migrations do, when to run
them, and how they compose with Kotte's existing setup tooling.

## TL;DR

From the repo root (one-liner via the Makefile, which handles `cd` and the venv for you):

```bash
export DB_HOST=… DB_PORT=… DB_NAME=… DB_USER=… DB_PASSWORD=…
make migrate-up
```

Or directly via the Alembic CLI (from `backend/` with the venv active):

```bash
cd backend
. venv/bin/activate
export DB_HOST=… DB_PORT=… DB_NAME=… DB_USER=… DB_PASSWORD=…
alembic upgrade head
```

That's it. Alembic runs the full migration chain (currently two
migrations), is idempotent, and touches nothing in the user's existing
AGE graphs.

## The mental model

**Kotte does not own a database.** Every request connects to an AGE
database that the _user_ supplies at login time. That shapes everything
else in this document, so let's be explicit about the two kinds of
schema involved:

1. **The user's data** — graphs, vertices, edges, label tables. Kotte
   reads this heavily but never modifies anything except via explicit
   Cypher queries run by the user. Migrations **never touch** this
   data.
2. **Kotte's auxiliary schema** — the AGE extension itself and a few
   Kotte-owned tables (prefixed `kotte_` so they can't collide with the
   user's own `users` / `sessions` / etc.). This is what the migrations
   manage.

The migration chain is designed to be safe to run against any AGE
database — a brand-new one, a long-lived production one, or a shared
instance that also hosts unrelated services.

## Why alembic is operator tooling (not a runtime hook)

You might expect the backend to run `alembic upgrade head` automatically
at startup — that's what most FastAPI templates do. Kotte deliberately
doesn't, for three reasons:

1. **Kotte connects to many databases, not one.** A runtime hook would
   have to know _which_ database to migrate, but the backend sees a new
   connection URL on every user login. Blanket-migrating whatever comes
   in would surprise users who reuse databases across tools.
2. **Migration privileges are rare in prod.** Production AGE users
   often have `SELECT` / `INSERT` grants but not `CREATE EXTENSION`.
   Silently failing the hook on every login would be noisy; surfacing
   the failure as an error would block logins.
3. **Deploys and schema changes should be decoupled.** Running schema
   changes only when an operator explicitly asks makes rollbacks easy
   and avoids the "deploy broke because alembic couldn't run" class of
   incident.

A runtime hook gated on `RUN_MIGRATIONS=true` against a specific
`KOTTE_MIGRATION_DB_URL` is a reasonable future enhancement — mentioned
as a follow-up but not included in B7.

## How the connection URL is resolved

`backend/alembic/env.py:_resolve_url()` walks a fallback chain, first
match wins:

1. `alembic -x url=postgresql+psycopg://...` on the CLI.
2. `ALEMBIC_SQLALCHEMY_URL` environment variable.
3. `sqlalchemy.url` in `alembic.ini` (if it's been overridden from the
   shipped `driver://user:pass@localhost/dbname` placeholder).
4. Assembled from the same `DB_HOST` / `DB_PORT` / `DB_NAME` /
   `DB_USER` / `DB_PASSWORD` env vars that
   `scripts/migrate_add_indices.py` already reads. Passwords are
   URL-encoded so special characters don't break the DSN.

The driver prefix is `postgresql+psycopg://…` because the rest of the
backend runs on psycopg3. SQLAlchemy is used only as alembic's engine
façade — there are no ORM models or `target_metadata` in play.

## The migration chain

### `2c3c565210b1` — enable age extension

```sql
CREATE EXTENSION IF NOT EXISTS age;
```

This is a no-op on databases where AGE is already installed, which is
the common case. It exists so that a brand-new Postgres instance can
become Kotte-ready with a single `make migrate-up` — no hand-curated
`CREATE EXTENSION` needed first.

Downgrade is intentionally a no-op: `DROP EXTENSION age CASCADE` would
delete every graph in the database, which is a catastrophic data-loss
operation that should never happen via a routine `alembic downgrade -1`.
Operators who really want to uninstall AGE can do it by hand.

### `78c03fa27fda` — create `kotte_users` stub

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE TABLE IF NOT EXISTS kotte_users (
    id            BIGSERIAL    PRIMARY KEY,
    username      CITEXT       NOT NULL UNIQUE,
    password_hash TEXT         NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ  NULL
);
```

Forward-plumbing for Milestone D's multi-user work. **The app does not
read from or write to this table yet.** Laying the schema down early
means the first PR that actually wires authentication isn't also
landing a new migration + new code + a rollout story.

Naming: every table in this chain is `kotte_`-prefixed so it can't
collide with the user's own schema. Some target databases already have
a `users` table for unrelated purposes; we never want to touch it.

Downgrade drops the table cleanly (it's always empty for now). `citext`
is deliberately left installed — it's cheap, other extensions
sometimes depend on it, and dropping extensions on downgrade is
brittle.

## Adding a new migration

```bash
make migrate-new MSG="add kotte_sessions table"
# edit backend/alembic/versions/<rev>_add_kotte_sessions_table.py
```

Two ground rules:

1. **Raw SQL only.** Migrations are hand-written `op.execute(...)`
   blocks. Don't introduce SQLAlchemy models or `--autogenerate`; our
   target isn't an ORM-managed schema and the diff would be useless.
2. **Use `IF NOT EXISTS` / `IF EXISTS`.** Migrations run against
   already-populated databases more often than not. Every
   `CREATE TABLE`, `CREATE EXTENSION`, `CREATE INDEX`, etc. should be
   idempotent so re-running the chain (or running it after a partial
   manual fix) is safe.

## What's _not_ a migration

### Label indices

`scripts/migrate_add_indices.py` (also runnable as `make
reindex-labels`) walks `ag_catalog.ag_graph` + `ag_catalog.ag_label`
and creates `id` / `start_id` / `end_id` indices on every existing
vertex and edge label.

This can't be a static alembic migration because the catalog is
dynamic — the labels that exist depend on what the user has created,
and new labels keep appearing as Cypher queries run. An alembic
migration would be frozen at authoring time and miss everything added
afterwards.

Think of the two tools as complementary:

| Tool                   | What it does                               | When to run                |
|------------------------|--------------------------------------------|----------------------------|
| `make migrate-up`      | Apply versioned schema changes             | Once per deployment        |
| `make reindex-labels`  | Refresh indices from live catalog state    | Whenever new labels appear |

### Session storage

Sessions currently live in process memory (`session_manager`). They're
not persisted — a backend restart evicts every logged-in user. Swapping
to a Postgres-backed session store would warrant a new migration for a
`kotte_sessions` table; until then, no migration work is needed.

### Credentials

Saved database connections live in an encrypted JSON file
(`data/connections.json`) managed by `CredentialStorage`. Moving that
to Postgres would also add a migration. Again, not scoped into B7.

## Offline SQL review

Alembic can emit the SQL it _would_ run without connecting to anything,
which is useful when the CI runner can't reach the production AGE DB
but a DBA still needs to approve the migration:

```bash
alembic upgrade head --sql > pending-migration.sql
```

The output is a single transaction per migration with
`alembic_version` table updates included. Paste it into a review tool
or run it by hand with `psql -f pending-migration.sql`.

## Known limitations

- **No runtime hook.** See [_Why alembic is operator tooling_](#why-alembic-is-operator-tooling-not-a-runtime-hook) above. If your deployment is a single Kotte instance pointed at a single dedicated AGE DB, you can wire one in the Docker entrypoint.
- **No autogenerate.** Autogenerate diffs SQLAlchemy metadata against a target DB — we have neither the source-of-truth metadata nor any intent to build it.
- **Requires `CREATE EXTENSION` privilege.** The first migration
  (`CREATE EXTENSION IF NOT EXISTS age`) needs the DB role to have
  rights on extensions. Most managed Postgres services grant this to
  the owner role but not to read-only roles — connect as the owner
  when running migrations.
- **Not yet wired into CI.** The ROADMAP's B1.3 integration job will
  start an AGE service container with pre-applied migrations; that's
  tracked separately.

## See also

- `backend/alembic.ini` — shipped config, mostly defaults.
- `backend/alembic/env.py` — URL resolution and online/offline drivers.
- `backend/alembic/versions/` — the migrations themselves.
- `docs/ROADMAP.md` §B7 — the ticket that produced all of this.
