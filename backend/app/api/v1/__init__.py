"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1 import auth, graph, query, session, connections, health
from app.api.v1.import_router import router as import_router

router = APIRouter()

# Health checks (no prefix, no auth required)
router.include_router(health.router, tags=["health"])

# Protected routes
router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(session.router, prefix="/session", tags=["session"])
router.include_router(connections.router, prefix="/connections", tags=["connections"])
router.include_router(graph.router, prefix="/graphs", tags=["graphs"])
router.include_router(query.router, prefix="/queries", tags=["queries"])
router.include_router(import_router, prefix="/import", tags=["import"])

