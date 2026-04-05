from __future__ import annotations

from fastapi import APIRouter

from sodar.api.system import router as system_router
from sodar.api.indexer import router as indexer_router
from sodar.api.search import router as search_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system_router)
api_router.include_router(indexer_router)
api_router.include_router(search_router)
