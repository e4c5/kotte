"""Alembic environment for Kotte (ROADMAP B7).

Migrations run against a **user-supplied AGE database** — Kotte does not
own a database of its own. The connection URL is assembled from the
standard DB_* environment variables (the same ones `scripts/
migrate_add_indices.py` reads) so operators can point `alembic upgrade`
at any target without editing `alembic.ini`:

    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Override paths (first match wins):

    1. `-x url=postgresql+psycopg://...` passed to alembic on the CLI
    2. `ALEMBIC_SQLALCHEMY_URL` environment variable
    3. `sqlalchemy.url` in `alembic.ini`
    4. Built from DB_* env vars (the common case)

The driver is `psycopg` (psycopg3) so the URL prefix is
`postgresql+psycopg://…` — matches the rest of the backend.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# We don't use a SQLAlchemy metadata object — migrations are raw SQL via
# `op.execute(...)` because Kotte has no ORM. `autogenerate` is therefore
# intentionally unsupported; use `alembic revision -m "..."` (no
# `--autogenerate`) to add a new migration.
target_metadata = None


def _resolve_url() -> str:
    """Resolve the target database URL per the fallback chain in the docstring."""
    x_args = context.get_x_argument(as_dictionary=True)
    if "url" in x_args:
        return x_args["url"]

    env_url = os.environ.get("ALEMBIC_SQLALCHEMY_URL")
    if env_url:
        return env_url

    ini_url = config.get_main_option("sqlalchemy.url") or ""
    # The shipped alembic.ini leaves `sqlalchemy.url = driver://user:pass@
    # localhost/dbname` as a placeholder — ignore that and build from
    # DB_* env vars unless the operator has overridden it to something
    # real.
    if ini_url and not ini_url.startswith("driver://"):
        return ini_url

    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    database = os.environ.get("DB_NAME", "postgres")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "")

    # URL-encode so special characters in the password don't break the
    # DSN. The rest of the backend uses a dict-style connection so this
    # is the only spot that cares.
    auth = quote_plus(user)
    if password:
        auth = f"{auth}:{quote_plus(password)}"

    return f"postgresql+psycopg://{auth}@{host}:{port}/{database}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout without talking to a live database.

    Useful for generating a reviewable script (`alembic upgrade head --sql
    > migration.sql`) that an operator runs by hand in environments where
    the CI runner can't reach the production AGE DB.
    """
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the target and run the migrations."""
    # Override the ini URL so `engine_from_config` picks up our resolved
    # value. `pool.NullPool` keeps alembic from holding a connection
    # open past the migration run — important for one-shot CLI use.
    ini_section = config.get_section(config.config_ini_section, {}) or {}
    ini_section["sqlalchemy.url"] = _resolve_url()

    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
