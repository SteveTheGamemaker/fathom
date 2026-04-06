from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import select

import fathom.database as db
from fathom.api.router import api_router
from fathom.models import Base  # imports all models, registering them with metadata
from fathom.models.quality import DEFAULT_PROFILES, QualityProfile, QualityProfileItem

STATIC_DIR = Path(__file__).parent / "static"


async def _seed_quality_profiles():
    """Seed default quality profiles if none exist."""
    async with db.async_session() as session:
        result = await session.execute(select(QualityProfile).limit(1))
        if result.scalars().first() is not None:
            return  # already seeded

        for profile_data in DEFAULT_PROFILES:
            profile = QualityProfile(name=profile_data["name"], cutoff=profile_data["cutoff"])
            session.add(profile)
            await session.flush()
            for item_data in profile_data["items"]:
                item = QualityProfileItem(profile_id=profile.id, **item_data)
                session.add(item)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Create tables on startup (Alembic handles migrations in production,
    # but this ensures the DB works for development without running migrations)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_quality_profiles()

    # Start background scheduler
    from fathom.scheduler.setup import start_scheduler, stop_scheduler
    start_scheduler()

    yield

    stop_scheduler()
    await db.engine.dispose()


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Require API key for /api/ routes when auth.api_key is configured."""

    async def dispatch(self, request: Request, call_next):
        from fathom.config import settings
        api_key = settings.auth.api_key
        if not api_key:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        # Check header or query param
        provided = request.headers.get("X-Api-Key") or request.query_params.get("apikey")
        if provided != api_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

        return await call_next(request)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fathom",
        description="Lightweight Sonarr+Radarr replacement with LLM-powered release parsing",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(ApiKeyMiddleware)
    app.include_router(api_router)

    # Web UI
    from fathom.web.routes import router as web_router
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
