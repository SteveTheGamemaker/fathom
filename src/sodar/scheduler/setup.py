"""APScheduler setup — registers all background jobs on the async event loop."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from sodar.config import settings

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _register_jobs() -> None:
    """Register all recurring jobs. Import here to avoid circular imports."""
    from sodar.scheduler.rss_sync import rss_sync_job
    from sodar.scheduler.search_missing import search_missing_job
    from sodar.scheduler.import_check import import_check_job

    cfg = settings.scheduler

    scheduler.add_job(
        rss_sync_job,
        trigger=IntervalTrigger(minutes=cfg.rss_sync_interval_minutes),
        id="rss_sync",
        name="RSS Sync",
        replace_existing=True,
    )

    scheduler.add_job(
        search_missing_job,
        trigger=IntervalTrigger(hours=cfg.search_missing_interval_hours),
        id="search_missing",
        name="Search Missing",
        replace_existing=True,
    )

    scheduler.add_job(
        import_check_job,
        trigger=IntervalTrigger(seconds=cfg.import_check_interval_seconds),
        id="import_check",
        name="Import Check",
        replace_existing=True,
    )

    log.info(
        "Scheduler jobs registered: RSS every %dm, Search Missing every %dh, Import Check every %ds",
        cfg.rss_sync_interval_minutes,
        cfg.search_missing_interval_hours,
        cfg.import_check_interval_seconds,
    )


def start_scheduler() -> None:
    """Register jobs and start the scheduler."""
    _register_jobs()
    scheduler.start()
    log.info("Scheduler started")


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler stopped")
