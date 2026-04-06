"""RSS Sync job — polls all enabled indexers and auto-grabs releases for monitored media."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import fathom.database as db
from fathom.downloaders import make_downloader
from fathom.indexers.torznab import TorznabClient
from fathom.indexers.newznab import NewznabClient
from fathom.llm.matcher import rank_releases
from fathom.llm.parser import parse_releases
from fathom.models.download import DownloadClient, DownloadRecord
from fathom.models.indexer import Indexer
from fathom.models.media import Episode, MediaStatus, Movie, Season, Series
from fathom.models.quality import QualityProfile

log = logging.getLogger(__name__)


def _make_indexer_client(indexer: Indexer):
    if indexer.type == "newznab":
        return NewznabClient(
            name=indexer.name, base_url=indexer.base_url,
            api_key=indexer.api_key, categories=indexer.categories,
        )
    return TorznabClient(
        name=indexer.name, base_url=indexer.base_url,
        api_key=indexer.api_key, categories=indexer.categories,
    )


async def _get_enabled_download_client(session) -> DownloadClient | None:
    result = await session.execute(
        select(DownloadClient).where(DownloadClient.enabled == True).limit(1)
    )
    return result.scalars().first()


async def _search_indexer(indexer: Indexer, query: str) -> list:
    client = _make_indexer_client(indexer)
    try:
        return await client.search(query)
    except Exception:
        log.exception("RSS sync: indexer %s search failed", indexer.name)
        return []
    finally:
        await client.close()


async def _grab_best(
    session,
    results: list,
    parsed: dict,
    profile: QualityProfile,
    current_quality: str | None,
    dl_client: DownloadClient,
    media_type: str,
    movie_id: int | None = None,
    episode_id: int | None = None,
) -> bool:
    """Try to grab the best matching release. Returns True if grabbed."""
    # Attach seeders to parsed results for ranking
    for r in results:
        p = parsed.get(r.title)
        if p:
            p["seeders"] = r.seeders or 0
            p["size"] = r.size or 0
            p["download_url"] = r.download_url

    parsed_list = [parsed[r.title] for r in results if r.title in parsed]
    ranked = rank_releases(parsed_list, profile, current_quality)

    if not ranked:
        return False

    best = ranked[0]
    # Find the download_url from the parsed dict
    download_url = None
    for r in results:
        p = parsed.get(r.title)
        if p and p.get("raw_title") == best.raw_title:
            download_url = r.download_url
            break

    if not download_url:
        return False

    # Check we haven't already grabbed this
    existing = await session.execute(
        select(DownloadRecord).where(DownloadRecord.release_title == best.raw_title).limit(1)
    )
    if existing.scalars().first():
        return False

    downloader = make_downloader(dl_client)
    if not downloader:
        return False

    try:
        if dl_client.type == "sabnzbd":
            download_id = await downloader.add_nzb(download_url, category=dl_client.category)
        else:
            download_id = await downloader.add_torrent(download_url, category=dl_client.category)
    except Exception:
        log.exception("RSS sync: failed to send torrent to download client")
        return False
    finally:
        await downloader.close()

    record = DownloadRecord(
        media_type=media_type,
        movie_id=movie_id,
        episode_id=episode_id,
        download_client_id=dl_client.id,
        release_title=best.raw_title,
        download_url=download_url,
        download_id=download_id,
        quality=best.quality,
        status="queued",
    )
    session.add(record)
    log.info("RSS sync: grabbed %s (%s)", best.raw_title, best.quality)

    try:
        from fathom.services.notification_service import notify_grab
        await notify_grab(best.raw_title, best.quality)
    except Exception:
        pass

    return True


async def rss_sync_job() -> None:
    """Run one RSS sync cycle."""
    log.info("RSS sync starting")

    async with db.async_session() as session:
        # Get enabled indexers
        result = await session.execute(
            select(Indexer).where(Indexer.enabled == True).order_by(Indexer.priority)
        )
        indexers = result.scalars().all()
        if not indexers:
            log.debug("RSS sync: no enabled indexers")
            return

        # Get enabled download client
        dl_client = await _get_enabled_download_client(session)
        if not dl_client:
            log.debug("RSS sync: no enabled download client")
            return

        # --- Movies ---
        movies_result = await session.execute(
            select(Movie)
            .where(Movie.status == MediaStatus.MONITORED)
            .where(Movie.file_path == None)  # noqa: E711 — not downloaded yet
            .options(selectinload(Movie.quality_profile).selectinload(QualityProfile.items))
        )
        movies = movies_result.scalars().all()

        for movie in movies:
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

        # --- Series episodes ---
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

    log.info("RSS sync complete")
