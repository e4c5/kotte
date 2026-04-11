import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
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

def test_hsts_header_in_non_debug_mode(monkeypatch):
    # Mock settings.debug to False
    from app.core.config import settings
    monkeypatch.setattr(settings, "debug", False)
    
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    
    @app.get("/")
    async def index():
        return {"message": "ok"}
    
    client = TestClient(app)
    response = client.get("/")
    
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
