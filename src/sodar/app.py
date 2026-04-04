from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from sodar.api.router import api_router
from sodar.database import engine
from sodar.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Create tables on startup (Alembic handles migrations in production,
    # but this ensures the DB works for development without running migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="sodar",
        description="Lightweight Sonarr+Radarr replacement with LLM-powered release parsing",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app
