"""create kotte users stub

Creates an empty `kotte_users` table that the app does **not** currently
read from. This is forward-plumbing for the Milestone D multi-user work
(ROADMAP D1+) — laying down a stable schema early so the first PR that
actually wires authentication isn't simultaneously landing a new
migration + new code + a migration-rollout story.

Naming: the `kotte_` prefix is deliberate. The target database is
user-supplied and may already contain a `users` table that has nothing
to do with Kotte — we never want to collide with that. Every table this
migration chain creates must be `kotte_`-prefixed for the same reason.

Columns:
* `id`            — `BIGSERIAL` primary key. Surrogate key; do not expose
                     publicly.
* `username`      — `CITEXT UNIQUE NOT NULL`. Case-insensitive so
                     `Alice` and `alice` don't both register. `CITEXT`
                     is a Postgres contrib type; the migration loads it
                     first with `CREATE EXTENSION IF NOT EXISTS citext`
                     so we don't depend on it being pre-installed.
* `password_hash` — `TEXT NOT NULL`. Stored as a bcrypt/argon2 string;
                     the app code that eventually populates this will
                     pick the algorithm.
* `created_at`    — `TIMESTAMPTZ NOT NULL DEFAULT now()`.
* `last_login_at` — `TIMESTAMPTZ NULL`. Populated on successful login
                     when the auth code lands.

Because the app doesn't read from this table yet, there's no risk of
`upgrade()` being blocked by existing data — the table starts empty and
stays empty until D1 ships. `downgrade()` therefore drops it cleanly.

Revision ID: 78c03fa27fda
Revises: 2c3c565210b1
Create Date: 2026-04-20 22:37:09.881441

"""

from typing import Sequence, Union

from alembic import op

revision: str = "78c03fa27fda"
down_revision: Union[str, Sequence[str], None] = "2c3c565210b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create `kotte_users` + its supporting citext extension."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("""
        CREATE TABLE IF NOT EXISTS kotte_users (
            id            BIGSERIAL    PRIMARY KEY,
            username      CITEXT       NOT NULL UNIQUE,
            password_hash TEXT         NOT NULL,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            last_login_at TIMESTAMPTZ  NULL
        )
        """)


def downgrade() -> None:
    """Drop `kotte_users`. Leaves citext in place because other code may use it."""
    op.execute("DROP TABLE IF EXISTS kotte_users")
