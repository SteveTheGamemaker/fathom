from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sqlalchemy import select

import sodar.database as db
from sodar.api.router import api_router
from sodar.models import Base  # imports all models, registering them with metadata
from sodar.models.quality import DEFAULT_PROFILES, QualityProfile, QualityProfileItem

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
    from sodar.scheduler.setup import start_scheduler, stop_scheduler
    start_scheduler()

    yield

    stop_scheduler()
    await db.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="sodar",
        description="Lightweight Sonarr+Radarr replacement with LLM-powered release parsing",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)

    # Web UI
    from sodar.web.routes import router as web_router
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app
