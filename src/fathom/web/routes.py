"""Web UI routes — Jinja2 templates served via HTMX."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fathom.config import settings
from fathom.database import get_db_session
from fathom.indexers.torznab import TorznabClient
from fathom.indexers.newznab import NewznabClient
from fathom.llm.parser import parse_releases
from fathom.models.download import DownloadClient, DownloadRecord
from fathom.models.indexer import Indexer
from fathom.models.media import Episode, MediaStatus, Movie, Season, Series
from fathom.models.quality import QualityProfile, QualityProfileItem

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


# ─── Page Routes ────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_db_session)):
    movie_count = (await session.execute(select(func.count(Movie.id)))).scalar() or 0
    movies_wanted = (await session.execute(
        select(func.count(Movie.id)).where(Movie.file_path == None, Movie.status == MediaStatus.MONITORED)
    )).scalar() or 0

    series_count = (await session.execute(select(func.count(Series.id)))).scalar() or 0
    episodes_wanted = (await session.execute(
        select(func.count(Episode.id)).where(Episode.file_path == None, Episode.monitored == True)
    )).scalar() or 0

    queue_count = (await session.execute(
        select(func.count(DownloadRecord.id)).where(DownloadRecord.status.in_(["queued", "downloading"]))
    )).scalar() or 0

    indexer_count = (await session.execute(select(func.count(Indexer.id)))).scalar() or 0
    indexers_enabled = (await session.execute(
        select(func.count(Indexer.id)).where(Indexer.enabled == True)
    )).scalar() or 0

    history_result = await session.execute(
        select(DownloadRecord).order_by(DownloadRecord.added_at.desc()).limit(10)
    )
    history = history_result.scalars().all()

    # Scheduler info
    scheduler_jobs = []
    try:
        from fathom.scheduler.setup import scheduler
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if job.next_run_time else None,
            })
    except Exception:
        pass

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "movie_count": movie_count,
        "movies_wanted": movies_wanted,
        "series_count": series_count,
        "episodes_wanted": episodes_wanted,
        "queue_count": queue_count,
        "indexer_count": indexer_count,
        "indexers_enabled": indexers_enabled,
        "history": history,
        "scheduler_jobs": scheduler_jobs,
    })


@router.get("/movies", response_class=HTMLResponse)
async def movies_page(request: Request, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Movie).order_by(Movie.sort_title))
    movies = result.scalars().all()

    # Build a map of movie_id -> download status for active downloads
    active_statuses = ("queued", "downloading")
    dl_result = await session.execute(
        select(DownloadRecord)
        .where(DownloadRecord.media_type == "movie")
        .where(DownloadRecord.movie_id.isnot(None))
        .where(DownloadRecord.status.in_(active_statuses))
    )
    download_status = {r.movie_id: r.status for r in dl_result.scalars().all()}

    profiles_result = await session.execute(select(QualityProfile))
    profiles = profiles_result.scalars().all()

    return templates.TemplateResponse("movies.html", {
        "request": request,
        "active_page": "movies",
        "movies": movies,
        "profiles": profiles,
        "root_folders": settings.media.root_folders_movies,
        "download_status": download_status,
    })


@router.get("/series", response_class=HTMLResponse)
async def series_page(request: Request, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Series)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
        .order_by(Series.sort_title)
    )
    series_list = result.scalars().all()

    profiles_result = await session.execute(select(QualityProfile))
    profiles = profiles_result.scalars().all()

    return templates.TemplateResponse("series.html", {
        "request": request,
        "active_page": "series",
        "series_list": series_list,
        "profiles": profiles,
        "root_folders": settings.media.root_folders_series,
    })


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {
        "request": request,
        "active_page": "search",
    })


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request, session: AsyncSession = Depends(get_db_session)):
    queue_result = await session.execute(
        select(DownloadRecord)
        .where(DownloadRecord.status.in_(["queued", "downloading"]))
        .order_by(DownloadRecord.added_at.desc())
    )
    queue = queue_result.scalars().all()

    history_result = await session.execute(
        select(DownloadRecord).order_by(DownloadRecord.added_at.desc()).limit(50)
    )
    history = history_result.scalars().all()

    return templates.TemplateResponse("queue.html", {
        "request": request,
        "active_page": "queue",
        "queue": queue,
        "history": history,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: AsyncSession = Depends(get_db_session)):
    indexers = (await session.execute(select(Indexer).order_by(Indexer.priority))).scalars().all()
    download_clients = (await session.execute(select(DownloadClient))).scalars().all()
    profiles = (await session.execute(
        select(QualityProfile).options(selectinload(QualityProfile.items))
    )).scalars().all()

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_page": "settings",
        "indexers": indexers,
        "download_clients": download_clients,
        "profiles": profiles,
    })


# ─── HTMX Action Routes ────────────────────────────────────────

@router.post("/web/search", response_class=HTMLResponse)
async def web_search(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    query = form.get("query", "").strip()
    if not query:
        return HTMLResponse("")

    # Get enabled indexers
    result = await session.execute(select(Indexer).where(Indexer.enabled == True))
    indexers = result.scalars().all()

    async def _search_one(indexer: Indexer):
        if indexer.type == "newznab":
            client = NewznabClient(
                name=indexer.name, base_url=indexer.base_url,
                api_key=indexer.api_key, categories=indexer.categories,
            )
        else:
            client = TorznabClient(
                name=indexer.name, base_url=indexer.base_url,
                api_key=indexer.api_key, categories=indexer.categories,
            )
        try:
            return await client.search(query)
        finally:
            await client.close()

    indexer_results = await asyncio.gather(
        *[_search_one(idx) for idx in indexers],
        return_exceptions=True,
    )

    all_results = []
    for r in indexer_results:
        if isinstance(r, Exception):
            continue
        all_results.extend(r)

    if not all_results:
        return templates.TemplateResponse("partials/search_results.html", {
            "request": request, "results": [], "query": query, "total": 0,
        })

    release_names = [r.title for r in all_results]
    parsed = await parse_releases(session, release_names)
    await session.commit()

    results = []
    for r in all_results:
        p = parsed.get(r.title, {})
        results.append({
            "title": r.title,
            "download_url": r.download_url,
            "size": r.size,
            "seeders": r.seeders,
            "leechers": r.leechers,
            "indexer_name": r.indexer_name,
            "parsed_title": p.get("title"),
            "year": p.get("year"),
            "season": p.get("season"),
            "episode": p.get("episode"),
            "quality": p.get("quality", "unknown"),
            "codec": p.get("codec"),
            "parse_method": p.get("parse_method"),
        })

    results.sort(key=lambda x: (x["seeders"] or 0), reverse=True)

    return templates.TemplateResponse("partials/search_results.html", {
        "request": request, "results": results, "query": query, "total": len(results),
    })


@router.post("/web/grab", response_class=HTMLResponse)
async def web_grab(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    download_url = form.get("download_url", "")
    release_title = form.get("release_title", "")
    quality = form.get("quality", "unknown")

    dl_result = await session.execute(
        select(DownloadClient).where(DownloadClient.enabled == True).limit(1)
    )
    dl_client = dl_result.scalars().first()
    if not dl_client:
        return HTMLResponse('<span class="badge badge-red">No download client</span>')

    from fathom.downloaders.qbittorrent import QBittorrentClient
    downloader = QBittorrentClient(
        host=dl_client.host, port=dl_client.port,
        username=dl_client.username, password=dl_client.password,
        use_ssl=dl_client.use_ssl,
    )
    try:
        download_id = await downloader.add_torrent(download_url, category=dl_client.category)
    except Exception:
        return HTMLResponse('<span class="badge badge-red">Failed</span>')
    finally:
        await downloader.close()

    record = DownloadRecord(
        media_type="movie",
        download_client_id=dl_client.id,
        release_title=release_title,
        download_url=download_url,
        download_id=download_id,
        quality=quality,
        status="queued",
    )
    session.add(record)
    await session.commit()

    return HTMLResponse('<span class="badge badge-green">Grabbed!</span>')


def _sort_title(title: str) -> str:
    t = title.lower().strip()
    for article in ("the ", "a ", "an "):
        if t.startswith(article):
            t = t[len(article):]
            break
    return t


def _default_folder(title: str, year: int) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    return f"{safe} ({year})"


@router.post("/web/add-movie", response_class=HTMLResponse)
async def web_add_movie(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    tmdb_id = int(form.get("tmdb_id", 0))
    title = form.get("title", "")
    year = int(form.get("year", 0))
    overview = form.get("overview", "")
    poster_url = form.get("poster_url", "")
    imdb_id = form.get("imdb_id", "")
    quality_profile_id = int(form.get("quality_profile_id", 1))
    root_folder = form.get("root_folder", "/movies")

    existing = await session.execute(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if existing.scalars().first():
        return HTMLResponse('<div class="toast toast-error">Movie already exists</div>')

    movie = Movie(
        title=title, sort_title=_sort_title(title), year=year,
        tmdb_id=tmdb_id, imdb_id=imdb_id or None,
        overview=overview or None, poster_url=poster_url or None,
        quality_profile_id=quality_profile_id,
        root_folder=root_folder,
        folder_name=_default_folder(title, year),
    )
    session.add(movie)
    await session.commit()

    # Re-render movies page content
    return RedirectResponse("/movies", status_code=303)


@router.post("/web/add-series", response_class=HTMLResponse)
async def web_add_series(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    tvdb_id = int(form.get("tvdb_id", 0))
    tmdb_id = int(form.get("tmdb_id", 0)) if form.get("tmdb_id") else None
    title = form.get("title", "")
    year = int(form.get("year", 0))
    overview = form.get("overview", "")
    poster_url = form.get("poster_url", "")
    quality_profile_id = int(form.get("quality_profile_id", 1))
    root_folder = form.get("root_folder", "/tv")

    existing = await session.execute(select(Series).where(Series.tvdb_id == tvdb_id))
    if existing.scalars().first():
        return HTMLResponse('<div class="toast toast-error">Series already exists</div>')

    series = Series(
        title=title, sort_title=_sort_title(title), year=year,
        tvdb_id=tvdb_id, tmdb_id=tmdb_id,
        overview=overview or None, poster_url=poster_url or None,
        quality_profile_id=quality_profile_id,
        root_folder=root_folder,
        folder_name=_default_folder(title, year),
    )
    session.add(series)
    await session.flush()  # get series.id before adding seasons

    # Fetch seasons & episodes from TMDB
    if tmdb_id:
        from fathom.services.metadata_service import TMDBService
        tmdb = TMDBService(settings.tmdb.api_key)
        try:
            tv_info = await tmdb.get_tv(tmdb_id)
            for s_info in tv_info.get("seasons", []):
                season = Season(
                    series_id=series.id,
                    season_number=s_info["season_number"],
                    monitored=s_info["season_number"] > 0,  # skip specials by default
                )
                session.add(season)
                await session.flush()

                episodes = await tmdb.get_tv_season(tmdb_id, s_info["season_number"])
                for ep_info in episodes:
                    air_date = None
                    if ep_info.get("air_date"):
                        from datetime import date as date_type
                        try:
                            air_date = date_type.fromisoformat(ep_info["air_date"])
                        except ValueError:
                            pass
                    episode = Episode(
                        season_id=season.id,
                        series_id=series.id,
                        episode_number=ep_info["episode_number"],
                        title=ep_info.get("title"),
                        air_date=air_date,
                        overview=ep_info.get("overview") or None,
                        monitored=season.monitored,
                    )
                    session.add(episode)
        except Exception:
            log.exception("Failed to fetch seasons/episodes from TMDB for %s", title)
        finally:
            await tmdb.close()

    await session.commit()

    return RedirectResponse("/series", status_code=303)


@router.post("/web/add-indexer", response_class=HTMLResponse)
async def web_add_indexer(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    indexer = Indexer(
        name=form.get("name", ""),
        type=form.get("type", "torznab"),
        base_url=form.get("base_url", ""),
        api_key=form.get("api_key", ""),
        categories=form.get("categories", ""),
        priority=int(form.get("priority", 1)),
        enabled=True,
    )
    session.add(indexer)
    await session.commit()
    return RedirectResponse("/settings", status_code=303)


@router.post("/web/add-download-client", response_class=HTMLResponse)
async def web_add_download_client(request: Request, session: AsyncSession = Depends(get_db_session)):
    form = await request.form()
    client = DownloadClient(
        name=form.get("name", ""),
        type=form.get("type", "qbittorrent"),
        host=form.get("host", ""),
        port=int(form.get("port", 8080)),
        username=form.get("username") or None,
        password=form.get("password") or None,
        category=form.get("category") or None,
        enabled=True,
    )
    session.add(client)
    await session.commit()
    return RedirectResponse("/settings", status_code=303)


# ─── TMDB Search (for add-movie/add-series modals) ─────────────

@router.get("/web/search-tmdb-movie", response_class=HTMLResponse)
async def search_tmdb_movie(request: Request):
    query = request.query_params.get("q", "").strip()
    if not query or len(query) < 2:
        return HTMLResponse("")

    if not settings.tmdb.api_key:
        return HTMLResponse('<div class="text-muted text-sm" style="padding:12px;">TMDB API key not configured</div>')

    from fathom.services.metadata_service import TMDBService
    tmdb = TMDBService(settings.tmdb.api_key)
    try:
        results = await tmdb.search_movie(query)
        # Enrich first few with imdb_id
        enriched = []
        for m in results[:8]:
            try:
                detail = await tmdb.get_movie(m["tmdb_id"])
                m["imdb_id"] = detail.get("imdb_id")
                m["id"] = m["tmdb_id"]
            except Exception:
                m["id"] = m["tmdb_id"]
            enriched.append(m)
        return templates.TemplateResponse("partials/tmdb_movie_results.html", {
            "request": request, "results": enriched, "query": query,
        })
    except Exception as e:
        log.exception("TMDB movie search failed")
        return HTMLResponse(f'<div class="text-muted text-sm" style="padding:12px;">TMDB search failed: {e}</div>')
    finally:
        await tmdb.close()


@router.get("/web/search-tmdb-tv", response_class=HTMLResponse)
async def search_tmdb_tv(request: Request):
    query = request.query_params.get("q", "").strip()
    if not query or len(query) < 2:
        return HTMLResponse("")

    if not settings.tmdb.api_key:
        return HTMLResponse('<div class="text-muted text-sm" style="padding:12px;">TMDB API key not configured</div>')

    from fathom.services.metadata_service import TMDBService
    tmdb = TMDBService(settings.tmdb.api_key)
    try:
        results = await tmdb.search_tv(query)
        enriched = []
        for s in results[:8]:
            try:
                detail = await tmdb.get_tv(s["tmdb_id"])
                s["tvdb_id"] = detail.get("tvdb_id")
                s["tmdb_id"] = s["tmdb_id"]
            except Exception:
                s["tvdb_id"] = 0
            enriched.append(s)
        return templates.TemplateResponse("partials/tmdb_tv_results.html", {
            "request": request, "results": enriched, "query": query,
        })
    except Exception as e:
        log.exception("TMDB TV search failed")
        return HTMLResponse(f'<div class="text-muted text-sm" style="padding:12px;">TMDB search failed: {e}</div>')
    finally:
        await tmdb.close()
