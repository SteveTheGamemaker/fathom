from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sodar.database import get_db_session
from sodar.downloaders.qbittorrent import QBittorrentClient
from sodar.models.download import DownloadClient, DownloadRecord
from sodar.schemas.download import (
    DownloadClientCreate,
    DownloadClientResponse,
    DownloadClientUpdate,
    DownloadRecordResponse,
    GrabRequest,
    QueueItemResponse,
)

log = logging.getLogger(__name__)

router = APIRouter(tags=["downloads"])


def _make_downloader(client: DownloadClient):
    if client.type == "qbittorrent":
        return QBittorrentClient(
            host=client.host,
            port=client.port,
            username=client.username,
            password=client.password,
            use_ssl=client.use_ssl,
        )
    raise HTTPException(400, f"Unsupported download client type: {client.type}")


# --- Download Client CRUD ---

@router.get("/download-client", response_model=list[DownloadClientResponse])
async def list_download_clients(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(DownloadClient))
    return result.scalars().all()


@router.post("/download-client", response_model=DownloadClientResponse, status_code=201)
async def create_download_client(
    data: DownloadClientCreate,
    session: AsyncSession = Depends(get_db_session),
):
    client = DownloadClient(**data.model_dump())
    session.add(client)
    await session.flush()
    await session.refresh(client)
    return client


@router.get("/download-client/{client_id}", response_model=DownloadClientResponse)
async def get_download_client(client_id: int, session: AsyncSession = Depends(get_db_session)):
    client = await session.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(404, "Download client not found")
    return client


@router.put("/download-client/{client_id}", response_model=DownloadClientResponse)
async def update_download_client(
    client_id: int,
    data: DownloadClientUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    client = await session.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(404, "Download client not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    await session.flush()
    await session.refresh(client)
    return client


@router.delete("/download-client/{client_id}", status_code=204)
async def delete_download_client(client_id: int, session: AsyncSession = Depends(get_db_session)):
    client = await session.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(404, "Download client not found")
    await session.delete(client)


@router.post("/download-client/{client_id}/test")
async def test_download_client(client_id: int, session: AsyncSession = Depends(get_db_session)):
    client = await session.get(DownloadClient, client_id)
    if not client:
        raise HTTPException(404, "Download client not found")
    downloader = _make_downloader(client)
    try:
        ok = await downloader.test_connection()
        return {"success": ok}
    finally:
        if hasattr(downloader, "close"):
            await downloader.close()


# --- Grab (send to download client) ---

@router.post("/grab", response_model=DownloadRecordResponse)
async def grab_release(
    data: GrabRequest,
    session: AsyncSession = Depends(get_db_session),
):
    # Find download client
    if data.download_client_id:
        dl_client = await session.get(DownloadClient, data.download_client_id)
        if not dl_client:
            raise HTTPException(404, "Download client not found")
    else:
        result = await session.execute(
            select(DownloadClient).where(DownloadClient.enabled == True).limit(1)
        )
        dl_client = result.scalars().first()
        if not dl_client:
            raise HTTPException(400, "No enabled download client configured")

    downloader = _make_downloader(dl_client)
    try:
        download_id = await downloader.add_torrent(data.download_url, category=dl_client.category)
    finally:
        if hasattr(downloader, "close"):
            await downloader.close()

    record = DownloadRecord(
        media_type=data.media_type,
        movie_id=data.movie_id,
        episode_id=data.episode_id,
        indexer_id=data.indexer_id,
        download_client_id=dl_client.id,
        release_title=data.release_title,
        download_url=data.download_url,
        download_id=download_id,
        quality=data.quality,
        status="queued",
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


# --- Queue ---

@router.get("/queue", response_model=list[QueueItemResponse])
async def get_queue(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(DownloadRecord)
        .where(DownloadRecord.status.in_(["queued", "downloading"]))
        .order_by(DownloadRecord.added_at.desc())
    )
    records = result.scalars().all()

    items = []
    for record in records:
        items.append(QueueItemResponse(
            id=record.id,
            release_title=record.release_title,
            quality=record.quality,
            status=record.status,
            download_id=record.download_id,
        ))
    return items


@router.get("/history", response_model=list[DownloadRecordResponse])
async def get_history(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(DownloadRecord).order_by(DownloadRecord.added_at.desc()).limit(100)
    )
    return result.scalars().all()
