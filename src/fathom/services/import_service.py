"""Import service — handles post-download processing.

When a download completes, this service renames/moves the file using
the configured templates and updates the media record.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fathom.config import settings
from fathom.models.download import DownloadRecord
from fathom.models.media import Episode, Movie, Season, Series

log = logging.getLogger(__name__)


def _safe_filename(name: str) -> str:
    """Strip characters that are illegal in file/folder names."""
    return re.sub(r'[<>:"/\\|?*]', "", name).strip(". ")


def _find_media_file(source_path: str) -> Path | None:
    """Given a download path (file or folder), find the main media file."""
    src = Path(source_path)
    if not src.exists():
        return None

    if src.is_file():
        return src

    # It's a folder — find the largest media file
    media_exts = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".flv", ".webm", ".ts"}
    candidates = [f for f in src.rglob("*") if f.suffix.lower() in media_exts and f.is_file()]
    if not candidates:
        return None

    return max(candidates, key=lambda f: f.stat().st_size)


def _build_movie_path(movie: Movie, quality: str, ext: str) -> Path:
    """Build the destination path for a movie using the rename template."""
    template = settings.media.rename_movies
    dest_rel = template.format(
        title=_safe_filename(movie.title),
        year=movie.year,
        quality=quality or "unknown",
        ext=ext,
    )
    return Path(movie.root_folder) / dest_rel


def _build_episode_path(
    series: Series, season_number: int, episode: Episode, quality: str, ext: str,
) -> Path:
    """Build the destination path for an episode using the rename template."""
    template = settings.media.rename_episodes
    dest_rel = template.format(
        series=_safe_filename(series.title),
        season=season_number,
        episode=episode.episode_number,
        episode_title=_safe_filename(episode.title or ""),
        quality=quality or "unknown",
        ext=ext,
    )
    return Path(series.root_folder) / dest_rel


def _move_file(source: Path, dest: Path) -> bool:
    """Move a file to the destination, creating directories as needed."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        log.info("Moved: %s → %s", source, dest)
        return True
    except Exception:
        log.exception("Failed to move %s → %s", source, dest)
        return False


async def import_completed_download(
    session: AsyncSession,
    record: DownloadRecord,
    save_path: str,
) -> bool:
    """Move the downloaded file and update the media record.

    Args:
        session: DB session.
        record: The DownloadRecord that completed.
        save_path: The file/folder path from the download client.

    Returns:
        True if successfully imported.
    """
    now = datetime.now(timezone.utc)

    # Try to find the actual media file
    media_file = _find_media_file(save_path)
    ext = media_file.suffix.lstrip(".") if media_file else "mkv"

    if record.media_type == "movie" and record.movie_id:
        movie = await session.get(Movie, record.movie_id)
        if not movie:
            log.warning("Import: movie_id %d not found", record.movie_id)
            return False

        if media_file:
            dest = _build_movie_path(movie, record.quality, ext)
            if _move_file(media_file, dest):
                movie.file_path = str(dest)
            else:
                # Move failed — still record the download client's path
                movie.file_path = save_path
        else:
            movie.file_path = save_path

        movie.file_quality = record.quality
        movie.downloaded_at = now
        log.info("Imported movie: %s (%s)", movie.title, record.quality)

        from fathom.services.activity_service import log_activity
        await log_activity(
            session, "imported", f"Imported {movie.title} ({movie.year})",
            detail=record.quality, media_type="movie", movie_id=movie.id,
        )

        try:
            from fathom.services.notification_service import notify_import
            await notify_import(movie.title, record.quality, movie.file_path)
        except Exception:
            pass

    elif record.media_type == "episode" and record.episode_id:
        episode = await session.get(Episode, record.episode_id)
        if not episode:
            log.warning("Import: episode_id %d not found", record.episode_id)
            return False

        # Load the season and series for the rename template
        season = await session.get(Season, episode.season_id)
        series = await session.get(Series, episode.series_id) if episode.series_id else None

        if media_file and series and season:
            dest = _build_episode_path(series, season.season_number, episode, record.quality, ext)
            if _move_file(media_file, dest):
                episode.file_path = str(dest)
            else:
                episode.file_path = save_path
        else:
            episode.file_path = save_path

        episode.file_quality = record.quality
        title = f"{series.title} S{season.season_number:02d}E{episode.episode_number:02d}" if series and season else f"Episode {episode.id}"
        log.info("Imported episode: %s (%s)", title, record.quality)

        from fathom.services.activity_service import log_activity
        await log_activity(
            session, "imported", f"Imported {title}",
            detail=record.quality, media_type="episode", episode_id=episode.id,
        )

        try:
            from fathom.services.notification_service import notify_import
            await notify_import(title, record.quality, episode.file_path)
        except Exception:
            pass

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
