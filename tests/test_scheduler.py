"""Tests for the scheduler setup and import service."""

import pytest
from datetime import datetime, timezone

from sodar.models.download import DownloadClient, DownloadRecord
from sodar.models.media import Movie, MediaStatus
from sodar.services.import_service import import_completed_download


@pytest.mark.asyncio
async def test_import_completed_movie(db_session):
    """Import service updates movie file_path and quality on completion."""
    movie = Movie(
        title="The Matrix",
        sort_title="matrix",
        year=1999,
        tmdb_id=603,
        quality_profile_id=1,
        root_folder="/movies",
        folder_name="The Matrix (1999)",
        status=MediaStatus.MONITORED,
    )
    db_session.add(movie)
    await db_session.flush()

    dl_client = DownloadClient(
        name="Test qBit", type="qbittorrent",
        host="localhost", port=8080,
    )
    db_session.add(dl_client)
    await db_session.flush()

    record = DownloadRecord(
        media_type="movie",
        movie_id=movie.id,
        download_client_id=dl_client.id,
        release_title="The.Matrix.1999.1080p.BluRay.x265-RARBG",
        download_url="magnet:?xt=urn:btih:abc123",
        quality="bluray-1080p",
        status="downloading",
    )
    db_session.add(record)
    await db_session.flush()

    result = await import_completed_download(
        db_session, record, "/downloads/The.Matrix.1999.1080p.BluRay.x265-RARBG"
    )
    assert result is True
    assert record.status == "imported"
    assert record.imported_at is not None
    assert movie.file_path == "/downloads/The.Matrix.1999.1080p.BluRay.x265-RARBG"
    assert movie.file_quality == "bluray-1080p"


@pytest.mark.asyncio
async def test_import_missing_movie(db_session):
    """Import service returns False when the linked movie doesn't exist."""
    dl_client = DownloadClient(
        name="Test qBit", type="qbittorrent",
        host="localhost", port=8080,
    )
    db_session.add(dl_client)
    await db_session.flush()

    record = DownloadRecord(
        media_type="movie",
        movie_id=9999,  # doesn't exist
        download_client_id=dl_client.id,
        release_title="Fake.Movie.1080p",
        download_url="magnet:?xt=urn:btih:abc",
        quality="bluray-1080p",
        status="downloading",
    )
    db_session.add(record)
    await db_session.flush()

    result = await import_completed_download(db_session, record, "/downloads/fake")
    assert result is False


@pytest.mark.asyncio
async def test_scheduler_status_endpoint(client):
    """The /api/v1/system/scheduler endpoint returns scheduler info."""
    resp = await client.get("/api/v1/system/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    # Scheduler is stopped in tests, but the endpoint should still work
    assert "running" in data
    assert "jobs" in data


@pytest.mark.asyncio
async def test_scheduler_trigger_404(client):
    """Triggering a non-existent job returns 404."""
    resp = await client.post("/api/v1/system/scheduler/nonexistent/run")
    assert resp.status_code == 404
