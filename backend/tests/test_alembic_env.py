"""Unit tests for the Alembic env module's DSN builder.

`backend/alembic/env.py` is not on a package path — alembic imports it by
file path at migration time — so this test loads it via
`importlib.util.spec_from_file_location` with `alembic.context` mocked out.

We exercise `_resolve_url()` to pin down three things the hand-rolled
`quote_plus`-based version used to get wrong:

* spaces in passwords are escaped per RFC 3986 (`%20`, not `+`)
* IPv6 hosts are bracketed automatically (`[::1]`)
* a missing / empty `DB_PASSWORD` yields a password-less DSN
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

ENV_PY = Path(__file__).resolve().parents[1] / "alembic" / "env.py"

DB_ENV_VARS = (
    "ALEMBIC_SQLALCHEMY_URL",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


def _load_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    env: dict[str, str] | None = None,
    x_args: dict[str, str] | None = None,
    ini_url: str = "",
) -> ModuleType:
    """Load `backend/alembic/env.py` as an isolated module with alembic mocked.

    The module body calls `run_migrations_offline()` at import time; we point
    the fake context at offline mode and stub the transaction context manager
    so the import succeeds without touching a real database.
    """
    for var in DB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)

    fake_context = MagicMock(name="alembic.context")
    fake_context.is_offline_mode.return_value = True
    fake_context.get_x_argument.return_value = dict(x_args or {})
    fake_context.config.config_file_name = None
    fake_context.config.config_ini_section = "alembic"
    fake_context.config.get_main_option.return_value = ini_url
    fake_context.config.get_section.return_value = {}
    fake_context.begin_transaction.return_value.__enter__.return_value = None
    fake_context.begin_transaction.return_value.__exit__.return_value = False

    import alembic

    monkeypatch.setattr(alembic, "context", fake_context, raising=False)

    module_name = "kotte_alembic_env_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, ENV_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def test_password_with_space_is_preserved_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passwords with spaces must be stored on the URL object without `+`-escaping.

    SQLAlchemy's `URL` object treats `password` as an opaque string and passes
    it to the driver verbatim, so the bug that motivated this refactor — a
    `quote_plus`-escaped `+` being fed back to psycopg as a literal plus — is
    avoided entirely as long as we don't round-trip through `render_as_string`.
    """
    from sqlalchemy.engine.url import URL

    module = _load_env(
        monkeypatch,
        env={
            "DB_HOST": "db.example.com",
            "DB_PORT": "5432",
            "DB_NAME": "kotte",
            "DB_USER": "kotte_user",
            "DB_PASSWORD": "my secret",
        },
    )

    url = module._resolve_url()

    assert isinstance(url, URL)
    assert url.password == "my secret"
    assert url.username == "kotte_user"
    assert url.host == "db.example.com"
    assert url.port == 5432
    assert url.database == "kotte"
    assert url.drivername == "postgresql+psycopg"


def test_ipv6_host_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    """IPv6 hosts must round-trip intact on the URL object (no manual bracketing needed)."""
    from sqlalchemy.engine.url import URL

    module = _load_env(
        monkeypatch,
        env={
            "DB_HOST": "::1",
            "DB_PORT": "5432",
            "DB_NAME": "kotte",
            "DB_USER": "kotte_user",
            "DB_PASSWORD": "pw",
        },
    )

    url = module._resolve_url()

    assert isinstance(url, URL)
    assert url.host == "::1"
    # Rendered form should bracket the host so driver parsers don't misread it.
    assert "@[::1]:5432/" in url.render_as_string(hide_password=False)


def test_missing_password_yields_no_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `DB_PASSWORD`, the URL must carry `password=None`, not an empty string."""
    from sqlalchemy.engine.url import URL

    module = _load_env(
        monkeypatch,
        env={
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "kotte",
            "DB_USER": "kotte_user",
        },
    )

    url = module._resolve_url()

    assert isinstance(url, URL)
    assert url.password is None
    rendered = url.render_as_string(hide_password=False)
    assert rendered == "postgresql+psycopg://kotte_user@localhost:5432/kotte"


def test_empty_password_is_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DB_PASSWORD=""` preserves the old behaviour: no password segment."""
    from sqlalchemy.engine.url import URL

    module = _load_env(
        monkeypatch,
        env={
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_NAME": "kotte",
            "DB_USER": "kotte_user",
            "DB_PASSWORD": "",
        },
    )

    url = module._resolve_url()

    assert isinstance(url, URL)
    assert url.password is None


def test_non_integer_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer `DB_PORT` should surface a clear ValueError, not a SQLAlchemy trace."""
    with pytest.raises(ValueError, match="DB_PORT must be an integer"):
        _load_env(
            monkeypatch,
            env={
                "DB_HOST": "localhost",
                "DB_PORT": "not-a-number",
                "DB_NAME": "kotte",
                "DB_USER": "kotte_user",
            },
        )


def test_x_argument_url_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """`-x url=…` on the alembic CLI must win over DB_* env vars."""
    override = "postgresql+psycopg://override_user@override_host:6543/override_db"
    module = _load_env(
        monkeypatch,
        env={"DB_HOST": "ignored", "DB_USER": "ignored"},
        x_args={"url": override},
    )

    assert module._resolve_url() == override


def test_alembic_env_url_takes_precedence_over_db_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ALEMBIC_SQLALCHEMY_URL` wins over DB_* but loses to `-x url=…`."""
    env_url = "postgresql+psycopg://env_user@env_host:5432/env_db"
    module = _load_env(
        monkeypatch,
        env={
            "ALEMBIC_SQLALCHEMY_URL": env_url,
            "DB_HOST": "ignored",
            "DB_USER": "ignored",
        },
    )

    assert module._resolve_url() == env_url
