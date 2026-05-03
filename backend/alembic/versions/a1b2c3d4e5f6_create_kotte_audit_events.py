"""create kotte audit events

Creates `kotte_audit_events` for first-class audit logging (Milestone D5).

Every security-relevant event (CSRF failure, rate limit, auth, mutation,
credential CRUD) writes a row here. The five original `SECURITY:` log
sites in middleware.py / session.py / credentials.py are the primary
sources; login/logout/password-change events join once D1 ships.

Columns:
* `id`          — `BIGSERIAL` primary key.
* `event`       — short event code, e.g. `csrf_failure`, `rate_limit_ip`.
* `actor_id`    — Kotte user ID string; NULL for pre-auth or system events.
* `request_id`  — UUID linking this row to structured logs / OTEL traces.
* `payload`     — JSONB bag for event-specific fields (IP, path, query, …).
* `created_at`  — `TIMESTAMPTZ NOT NULL DEFAULT now()`.

Indexes:
* `(event, created_at)` — for event-type dashboards / alerting queries.
* `(actor_id, created_at)` — for per-user audit trails (NULL actors skipped).

Revision ID: a1b2c3d4e5f6
Revises: 78c03fa27fda
Create Date: 2026-05-02

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "78c03fa27fda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS kotte_audit_events (
            id         BIGSERIAL    PRIMARY KEY,
            event      TEXT         NOT NULL,
            actor_id   TEXT         NULL,
            request_id TEXT         NULL,
            payload    JSONB        NULL,
            created_at TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS kotte_audit_events_event_created_idx
            ON kotte_audit_events (event, created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS kotte_audit_events_actor_created_idx
            ON kotte_audit_events (actor_id, created_at)
            WHERE actor_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kotte_audit_events")
