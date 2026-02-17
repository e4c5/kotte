"""Tests for configuration."""

import os
import pytest
from unittest.mock import patch

from app.core.config import Settings


class TestSettings:
    """Tests for application settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.environment == "development"
        assert settings.db_host == "localhost"
        assert settings.db_port == 5432
        assert settings.query_timeout == 300
        assert settings.max_nodes_for_graph == 5000
        assert settings.max_edges_for_graph == 10000

    def test_session_secret_key_generation(self):
        """Test that session secret key is generated in development."""
        with patch.dict(os.environ, {}, clear=True):
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
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.max_nodes_for_graph == 10000
            assert settings.max_edges_for_graph == 20000


