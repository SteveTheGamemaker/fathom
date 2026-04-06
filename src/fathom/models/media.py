from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import String, Integer, Boolean, Date, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fathom.models.base import Base


class MediaStatus(str, enum.Enum):
    MONITORED = "monitored"
    UNMONITORED = "unmonitored"


class Movie(Base):
    __tablename__ = "movies"

    title: Mapped[str] = mapped_column(String)
    sort_title: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True)
    imdb_id: Mapped[str | None] = mapped_column(String, nullable=True)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[MediaStatus] = mapped_column(Enum(MediaStatus), default=MediaStatus.MONITORED)
    quality_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("quality_profiles.id"))
    root_folder: Mapped[str] = mapped_column(String)
    folder_name: Mapped[str] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_quality: Mapped[str | None] = mapped_column(String, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    quality_profile = relationship("QualityProfile")


class Series(Base):
    __tablename__ = "series"

    title: Mapped[str] = mapped_column(String)
    sort_title: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer)
    tvdb_id: Mapped[int] = mapped_column(Integer, unique=True)
    imdb_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[MediaStatus] = mapped_column(Enum(MediaStatus), default=MediaStatus.MONITORED)
    series_type: Mapped[str] = mapped_column(String, default="standard")  # standard | anime | daily
    quality_profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("quality_profiles.id"))
    root_folder: Mapped[str] = mapped_column(String)
    folder_name: Mapped[str] = mapped_column(String)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    quality_profile = relationship("QualityProfile")
    seasons: Mapped[list[Season]] = relationship(back_populates="series", cascade="all, delete-orphan")


class Season(Base):
    __tablename__ = "seasons"

    series_id: Mapped[int] = mapped_column(Integer, ForeignKey("series.id"))
    season_number: Mapped[int] = mapped_column(Integer)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)

    series: Mapped[Series] = relationship(back_populates="seasons")
    episodes: Mapped[list[Episode]] = relationship(back_populates="season", cascade="all, delete-orphan")


class Episode(Base):
    __tablename__ = "episodes"

    season_id: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.id"))
    series_id: Mapped[int] = mapped_column(Integer, ForeignKey("series.id"))
    episode_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    air_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    overview: Mapped[str | None] = mapped_column(String, nullable=True)
    monitored: Mapped[bool] = mapped_column(Boolean, default=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    file_quality: Mapped[str | None] = mapped_column(String, nullable=True)

    season: Mapped[Season] = relationship(back_populates="episodes")
