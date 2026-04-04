from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Boolean, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from sodar.models.base import Base


class ParsedRelease(Base):
    """Cache of parsed release names. Keyed by raw_title — a release name
    always parses to the same result, so this cache never invalidates."""

    __tablename__ = "parsed_releases"

    raw_title: Mapped[str] = mapped_column(String, unique=True, index=True)
    parsed_title: Mapped[str] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    episode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality: Mapped[str] = mapped_column(String, default="unknown")
    codec: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)
    release_group: Mapped[str | None] = mapped_column(String, nullable=True)
    is_proper: Mapped[bool] = mapped_column(Boolean, default=False)
    is_repack: Mapped[bool] = mapped_column(Boolean, default=False)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    parse_method: Mapped[str] = mapped_column(String, default="regex_fallback")
