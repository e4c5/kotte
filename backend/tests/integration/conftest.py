"""Integration test configuration and fixtures."""

import os
import pytest
import subprocess
import time
from typing import Generator

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def docker_compose():
    """Start Docker Compose services for integration tests."""
    compose_file = os.path.join(os.path.dirname(__file__), "..", "docker-compose.test.yml")
    
    # Start services
    subprocess.run(
        ["docker-compose", "-f", compose_file, "up", "-d"],
        check=True,
    )
    
    # Wait for services to be ready
    max_wait = 60
    elapsed = 0
    while elapsed < max_wait:
        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "ps", "-q", "postgres-test"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Check if postgres is healthy
            health_result = subprocess.run(
                ["docker-compose", "-f", compose_file, "exec", "-T", "postgres-test", "pg_isready", "-U", "test_user"],
                capture_output=True,
            )
            if health_result.returncode == 0:
                break
        time.sleep(2)
        elapsed += 2
    else:
        pytest.fail("Docker services did not become ready in time")
    
    yield
    
    # Stop services
    subprocess.run(
        ["docker-compose", "-f", compose_file, "down", "-v"],
        check=False,
    )


@pytest.fixture
def test_db_config(docker_compose):
    """Database configuration for integration tests."""
    return {
        "host": "localhost",
        "port": 5433,
        "database": "test_db",
        "user": "test_user",
        "password": "test_password",
    }


@pytest.fixture
def integration_client(test_db_config):
    """Test client configured for integration tests."""
    # Override database settings for integration tests
    os.environ.update({
        "DB_HOST": test_db_config["host"],
        "DB_PORT": str(test_db_config["port"]),
        "DB_NAME": test_db_config["database"],
        "DB_USER": test_db_config["user"],
        "DB_PASSWORD": test_db_config["password"],
    })
    
    return TestClient(app)

