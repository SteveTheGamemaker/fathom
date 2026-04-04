from __future__ import annotations

from fastapi import APIRouter

from sodar.api.system import router as system_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system_router)
