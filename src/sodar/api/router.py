from __future__ import annotations

from fastapi import APIRouter

from sodar.api.system import router as system_router
from sodar.api.indexer import router as indexer_router
from sodar.api.search import router as search_router
from sodar.api.media import router as media_router
from sodar.api.quality import router as quality_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system_router)
api_router.include_router(indexer_router)
api_router.include_router(search_router)
api_router.include_router(media_router)
api_router.include_router(quality_router)
