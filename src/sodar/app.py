from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from sqlalchemy import select

import sodar.database as db
from sodar.api.router import api_router
from sodar.models import Base  # imports all models, registering them with metadata
from sodar.models.quality import DEFAULT_PROFILES, QualityProfile, QualityProfileItem


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
    yield
    await db.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="sodar",
        description="Lightweight Sonarr+Radarr replacement with LLM-powered release parsing",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app
