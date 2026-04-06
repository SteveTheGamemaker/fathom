from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from fathom.models.base import Base


class DownloadClient(Base):
    __tablename__ = "download_clients"

    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # qbittorrent | transmission | sabnzbd
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    password: Mapped[str | None] = mapped_column(String, nullable=True)
    api_key: Mapped[str | None] = mapped_column(String, nullable=True)  # for SABnzbd
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DownloadRecord(Base):
    __tablename__ = "download_records"

    media_type: Mapped[str] = mapped_column(String)  # movie | episode
    movie_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("movies.id"), nullable=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("episodes.id"), nullable=True)
    indexer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("indexers.id"), nullable=True)
    download_client_id: Mapped[int] = mapped_column(Integer, ForeignKey("download_clients.id"))
    release_title: Mapped[str] = mapped_column(String)
    download_url: Mapped[str] = mapped_column(String)
    download_id: Mapped[str | None] = mapped_column(String, nullable=True)  # hash/ID from client
    quality: Mapped[str] = mapped_column(String, default="unknown")
    status: Mapped[str] = mapped_column(String, default="queued")  # queued | downloading | completed | failed | imported
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
