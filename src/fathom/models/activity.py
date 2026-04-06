from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from fathom.models.base import Base


class ActivityLog(Base):
    __tablename__ = "activity_log"

    event_type: Mapped[str] = mapped_column(String)  # grabbed | imported | added | failed | completed
    message: Mapped[str] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. quality, indexer name
    media_type: Mapped[str | None] = mapped_column(String, nullable=True)  # movie | episode
    movie_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
