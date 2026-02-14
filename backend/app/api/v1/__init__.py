"""API v1 routes."""

from fastapi import APIRouter

from app.api.v1 import graph, query, session

router = APIRouter()

router.include_router(session.router, prefix="/session", tags=["session"])
router.include_router(graph.router, prefix="/graphs", tags=["graphs"])
router.include_router(query.router, prefix="/queries", tags=["queries"])

