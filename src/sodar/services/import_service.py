"""Import service — handles post-download processing.

When a download completes, this service updates the media record
with the file path and quality information.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sodar.models.download import DownloadRecord
from sodar.models.media import Episode, Movie

log = logging.getLogger(__name__)


async def import_completed_download(
    session: AsyncSession,
    record: DownloadRecord,
    save_path: str,
) -> bool:
    """Mark a completed download as imported and update the media record.

    Args:
        session: DB session.
        record: The DownloadRecord that completed.
        save_path: The file/folder path from the download client.

    Returns:
        True if successfully imported.
    """
    now = datetime.now(timezone.utc)

    if record.media_type == "movie" and record.movie_id:
        movie = await session.get(Movie, record.movie_id)
        if movie:
            movie.file_path = save_path
            movie.file_quality = record.quality
            movie.downloaded_at = now
            log.info("Imported movie: %s → %s (%s)", movie.title, save_path, record.quality)
            try:
                from sodar.services.notification_service import notify_import
                await notify_import(movie.title, record.quality, save_path)
            except Exception:
                pass
        else:
            log.warning("Import: movie_id %d not found", record.movie_id)
            return False

    elif record.media_type == "episode" and record.episode_id:
        episode = await session.get(Episode, record.episode_id)
        if episode:
            episode.file_path = save_path
            episode.file_quality = record.quality
            log.info("Imported episode id %d → %s (%s)", episode.id, save_path, record.quality)
            try:
                from sodar.services.notification_service import notify_import
                await notify_import(f"Episode {episode.id}", record.quality, save_path)
            except Exception:
                pass
        else:
            log.warning("Import: episode_id %d not found", record.episode_id)
            return False
    else:
        log.warning("Import: record %d has no media link (type=%s)", record.id, record.media_type)
        return False

    record.status = "imported"
    record.imported_at = now
    return True


async def get_stale_downloads(session: AsyncSession, max_age_hours: int = 72) -> list[DownloadRecord]:
    """Find downloads that have been queued/downloading for too long."""
    cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
    result = await session.execute(
        select(DownloadRecord)
        .where(DownloadRecord.status.in_(["queued", "downloading"]))
    )
    records = result.scalars().all()
    stale = []
    for r in records:
        if r.added_at and r.added_at.timestamp() < cutoff:
            stale.append(r)
    return stale
