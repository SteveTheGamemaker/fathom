"""Search Missing job — searches indexers for monitored media without files.

Similar to RSS sync but runs less frequently and is meant to catch things
that RSS might have missed (e.g., media added after the RSS window).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import fathom.database as db
from fathom.models.download import DownloadClient, DownloadRecord
from fathom.models.indexer import Indexer
from fathom.models.media import Episode, MediaStatus, Movie, Season, Series
from fathom.models.quality import QualityProfile
from fathom.scheduler.rss_sync import (
    _get_enabled_download_client,
    _grab_best,
    _search_indexer,
)
from fathom.llm.parser import parse_releases

log = logging.getLogger(__name__)


async def search_missing_job() -> None:
    """Search for all monitored media that is missing files."""
    log.info("Search missing starting")

    async with db.async_session() as session:
        result = await session.execute(
            select(Indexer).where(Indexer.enabled == True).order_by(Indexer.priority)
        )
        indexers = result.scalars().all()
        if not indexers:
            log.debug("Search missing: no enabled indexers")
            return

        dl_client = await _get_enabled_download_client(session)
        if not dl_client:
            log.debug("Search missing: no enabled download client")
            return

        # Check if there's already an active download — skip if queue is busy
        active = await session.execute(
            select(DownloadRecord)
            .where(DownloadRecord.status.in_(["queued", "downloading"]))
            .limit(1)
        )
        if active.scalars().first():
            log.debug("Search missing: active downloads exist, skipping")
            return

        # --- Missing movies ---
        movies_result = await session.execute(
            select(Movie)
            .where(Movie.status == MediaStatus.MONITORED)
            .where(Movie.file_path == None)  # noqa: E711
            .options(selectinload(Movie.quality_profile).selectinload(QualityProfile.items))
        )
        movies = movies_result.scalars().all()
        log.info("Search missing: %d movies wanted", len(movies))

        for movie in movies:
            # Skip if we already have a pending download for this movie
            existing = await session.execute(
                select(DownloadRecord)
                .where(DownloadRecord.movie_id == movie.id)
                .where(DownloadRecord.status.in_(["queued", "downloading"]))
                .limit(1)
            )
            if existing.scalars().first():
                continue

            query = f"{movie.title} {movie.year}"
            all_results = []
            for indexer in indexers:
                results = await _search_indexer(indexer, query)
                all_results.extend(results)

            if not all_results:
                continue

            release_names = [r.title for r in all_results]
            parsed = await parse_releases(session, release_names)

            grabbed = await _grab_best(
                session, all_results, parsed, movie.quality_profile,
                movie.file_quality, dl_client, "movie", movie_id=movie.id,
            )
            if grabbed:
                await session.commit()

        # --- Missing episodes ---
        series_result = await session.execute(
            select(Series)
            .where(Series.status == MediaStatus.MONITORED)
            .options(
                selectinload(Series.seasons).selectinload(Season.episodes),
                selectinload(Series.quality_profile).selectinload(QualityProfile.items),
            )
        )
        all_series = series_result.scalars().all()

        for series in all_series:
            for season in series.seasons:
                if not season.monitored:
                    continue
                missing_eps = [ep for ep in season.episodes if ep.monitored and not ep.file_path]
                for ep in missing_eps:
                    # Skip if already downloading
                    existing = await session.execute(
                        select(DownloadRecord)
                        .where(DownloadRecord.episode_id == ep.id)
                        .where(DownloadRecord.status.in_(["queued", "downloading"]))
                        .limit(1)
                    )
                    if existing.scalars().first():
                        continue

                    query = f"{series.title} S{season.season_number:02d}E{ep.episode_number:02d}"
                    all_results = []
                    for indexer in indexers:
                        results = await _search_indexer(indexer, query)
                        all_results.extend(results)

                    if not all_results:
                        continue

                    release_names = [r.title for r in all_results]
                    parsed = await parse_releases(session, release_names)

                    grabbed = await _grab_best(
                        session, all_results, parsed, series.quality_profile,
                        ep.file_quality, dl_client, "episode", episode_id=ep.id,
                    )
                    if grabbed:
                        await session.commit()

    log.info("Search missing complete")
