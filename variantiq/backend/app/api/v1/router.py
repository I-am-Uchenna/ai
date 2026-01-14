"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import intelligence, query, variants

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    variants.router,
    prefix="/variants",
    tags=["variants"]
)

api_router.include_router(
    intelligence.router,
    prefix="/intelligence",
    tags=["intelligence"]
)

api_router.include_router(
    query.router,
    prefix="/query",
    tags=["query"]
)
