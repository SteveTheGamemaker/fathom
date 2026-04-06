"""Import Check job — polls download clients for completed downloads.

Runs frequently (every 60s by default). For each active download record,
checks if the download client reports it as complete, then triggers import.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

import sodar.database as db
from sodar.downloaders import make_downloader
from sodar.models.download import DownloadClient, DownloadRecord
from sodar.services.import_service import import_completed_download

log = logging.getLogger(__name__)


async def import_check_job() -> None:
    """Check download clients for completed downloads and import them."""
    async with db.async_session() as session:
        # Get active download records
        result = await session.execute(
            select(DownloadRecord).where(
                DownloadRecord.status.in_(["queued", "downloading"])
            )
        )
        active_records = result.scalars().all()

        if not active_records:
            return  # nothing to check

        # Group records by download client
        by_client: dict[int, list[DownloadRecord]] = {}
        for record in active_records:
            by_client.setdefault(record.download_client_id, []).append(record)

        for client_id, records in by_client.items():
            dl_client = await session.get(DownloadClient, client_id)
            if not dl_client:
                log.warning("Import check: download client %d not found", client_id)
                continue

            downloader = make_downloader(dl_client)
            if not downloader:
                log.warning("Import check: unsupported client type %s", dl_client.type)
                continue

            try:
                for record in records:
                    if not record.download_id:
                        # No hash — can't check status. Try to match by name
                        # from get_all if we have it. For now, skip.
                        continue

                    status = await downloader.get_status(record.download_id)
                    if not status:
                        continue

                    if status.status in ("completed", "seeding"):
                        # Download is done — import it
                        record.completed_at = datetime.now(timezone.utc)

                        if record.movie_id or record.episode_id:
                            imported = await import_completed_download(
                                session, record, status.save_path,
                            )
                            if not imported:
                                record.status = "completed"  # completed but not linked
                        else:
                            record.status = "completed"

                    elif status.status == "error":
                        record.status = "failed"
                        log.warning("Download failed: %s", record.release_title)

                    elif status.status == "downloading":
                        if record.status != "downloading":
                            record.status = "downloading"

                await session.commit()

            except Exception:
                log.exception("Import check failed for client %d", client_id)
            finally:
                await downloader.close()
