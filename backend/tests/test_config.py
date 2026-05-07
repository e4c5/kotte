"""Tests for configuration."""

import os
import pytest
from unittest.mock import patch

from app.core.config import Settings

# patch.dict(..., clear=True) removes keys set in conftest.py; include a dummy secret
# so Settings() does not emit UserWarning (generation path is covered elsewhere).
_TEST_SESSION_SECRET = "test-session-secret-key-for-config-tests-only-0123456789"


class TestSettings:
    """Tests for application settings."""

    def test_default_settings(self):
        """Test default settings values."""
        with patch.dict(
            os.environ,
            {"SESSION_SECRET_KEY": _TEST_SESSION_SECRET},
            clear=True,
        ):
            settings = Settings()
            assert settings.environment == "development"
            assert settings.db_host == "localhost"
            assert settings.db_port == 5432
            assert settings.query_timeout == 300
            assert settings.max_nodes_for_graph == 5000
            assert settings.max_edges_for_graph == 10000

    def test_session_secret_key_generation(self):
        """Test that session secret key is generated when unset (non-production)."""
        # ENVIRONMENT=test skips the dev UserWarning in Settings.__init__
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}, clear=True):
            settings = Settings()
            assert settings.session_secret_key is not None
            assert len(settings.session_secret_key) > 0

    def test_production_requires_secret_key(self):
        """Test that production requires explicit secret key."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert "SESSION_SECRET_KEY must be set" in str(exc_info.value)

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "test-host",
                "DB_PORT": "5433",
                "QUERY_TIMEOUT": "600",
                "SESSION_SECRET_KEY": _TEST_SESSION_SECRET,
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.db_host == "test-host"
            assert settings.db_port == 5433
            assert settings.query_timeout == 600

    def test_visualization_limits(self):
        """Test visualization limit settings."""
        settings = Settings()
        assert settings.max_nodes_for_graph == 5000
        assert settings.max_edges_for_graph == 10000

        with patch.dict(
            os.environ,
            {
                "MAX_NODES_FOR_GRAPH": "10000",
                "MAX_EDGES_FOR_GRAPH": "20000",
                "SESSION_SECRET_KEY": _TEST_SESSION_SECRET,
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.max_nodes_for_graph == 10000
            assert settings.max_edges_for_graph == 20000

    def test_pool_min_must_not_exceed_max(self):
        """Invalid pool bounds are rejected at settings load."""
        with patch.dict(
            os.environ,
            {"SESSION_SECRET_KEY": _TEST_SESSION_SECRET},
            clear=True,
        ):
            with pytest.raises(ValueError, match="db_pool_min_size"):
                Settings(
                    db_pool_min_size=10,
                    db_pool_max_size=5,
                )

    def test_cors_origins_json_array_form(self):
        """JSON-array string (the form pydantic-settings requires) is parsed correctly."""
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET_KEY": _TEST_SESSION_SECRET,
                "CORS_ORIGINS": '["https://example.com", "https://other.com"]',
            },
            clear=True,
        ):
            s = Settings()
            assert s.cors_origins == ["https://example.com", "https://other.com"]

    def test_cors_origins_comma_separated_form(self):
        """Comma-separated string (documented in CONFIGURATION.md) is also accepted."""
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET_KEY": _TEST_SESSION_SECRET,
                "CORS_ORIGINS": "https://example.com,https://other.com",
            },
            clear=True,
        ):
            s = Settings()
            assert s.cors_origins == ["https://example.com", "https://other.com"]

    def test_cors_origins_comma_separated_with_spaces(self):
        """Whitespace around commas is stripped."""
        with patch.dict(
            os.environ,
            {
                "SESSION_SECRET_KEY": _TEST_SESSION_SECRET,
                "CORS_ORIGINS": " https://a.com , https://b.com ",
            },
            clear=True,
        ):
            s = Settings()
            assert s.cors_origins == ["https://a.com", "https://b.com"]

    def test_cors_origins_list_passthrough(self):
        """A Python list (from direct Settings(...) instantiation) is passed through unchanged."""
        with patch.dict(os.environ, {"SESSION_SECRET_KEY": _TEST_SESSION_SECRET}, clear=True):
            s = Settings(cors_origins=["https://direct.com"])
            assert s.cors_origins == ["https://direct.com"]
