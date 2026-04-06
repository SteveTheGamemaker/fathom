from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DownloadClientCreate(BaseModel):
    name: str
    type: str  # qbittorrent | transmission | sabnzbd
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    use_ssl: bool = False
    category: str | None = None
    enabled: bool = True


class DownloadClientUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    use_ssl: bool | None = None
    category: str | None = None
    enabled: bool | None = None


class DownloadClientResponse(BaseModel):
    id: int
    name: str
    type: str
    host: str
    port: int
    username: str | None
    password: str | None
    api_key: str | None
    use_ssl: bool
    category: str | None
    enabled: bool

    model_config = {"from_attributes": True}


class GrabRequest(BaseModel):
    download_url: str
    release_title: str
    quality: str = "unknown"
    media_type: str = "movie"  # movie | episode
    movie_id: int | None = None
    episode_id: int | None = None
    indexer_id: int | None = None
    download_client_id: int | None = None  # None = use first enabled


class DownloadRecordResponse(BaseModel):
    id: int
    media_type: str
    movie_id: int | None
    episode_id: int | None
    indexer_id: int | None
    download_client_id: int
    release_title: str
    download_url: str
    download_id: str | None
    quality: str
    status: str
    added_at: datetime
    completed_at: datetime | None
    imported_at: datetime | None

    model_config = {"from_attributes": True}


class QueueItemResponse(BaseModel):
    id: int
    release_title: str
    quality: str
    status: str
    download_id: str | None
    progress: float | None = None
    size: int | None = None
    download_speed: int | None = None
    eta: int | None = None
