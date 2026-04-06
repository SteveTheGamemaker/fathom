"""Activity logging — records events for the dashboard activity feed."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from fathom.models.activity import ActivityLog


async def log_activity(
    session: AsyncSession,
    event_type: str,
    message: str,
    detail: str | None = None,
    media_type: str | None = None,
    movie_id: int | None = None,
    episode_id: int | None = None,
) -> None:
    entry = ActivityLog(
        event_type=event_type,
        message=message,
        detail=detail,
        media_type=media_type,
        movie_id=movie_id,
        episode_id=episode_id,
    )
    session.add(entry)
