import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware


def test_security_headers_middleware():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    async def index():
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers


def test_hsts_only_when_production_and_https(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    async def index():
        return {"message": "ok"}

    client = TestClient(app, base_url="https://testserver")
    response = client.get("/")

    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_no_hsts_on_http_even_in_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/")
    async def index():
        return {"message": "ok"}

    client = TestClient(app, base_url="http://testserver")
    response = client.get("/")

    assert "Strict-Transport-Security" not in response.headers
