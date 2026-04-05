from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class MovieCreate(BaseModel):
    title: str
    year: int
    tmdb_id: int
    imdb_id: str | None = None
    overview: str | None = None
    poster_url: str | None = None
    quality_profile_id: int
    root_folder: str
    folder_name: str | None = None  # auto-generated if not provided


class MovieResponse(BaseModel):
    id: int
    title: str
    sort_title: str
    year: int
    tmdb_id: int
    imdb_id: str | None
    overview: str | None
    poster_url: str | None
    status: str
    quality_profile_id: int
    root_folder: str
    folder_name: str
    file_path: str | None
    file_quality: str | None
    added_at: datetime
    downloaded_at: datetime | None

    model_config = {"from_attributes": True}


class SeriesCreate(BaseModel):
    title: str
    year: int
    tvdb_id: int
    tmdb_id: int | None = None
    imdb_id: str | None = None
    overview: str | None = None
    poster_url: str | None = None
    series_type: str = "standard"
    quality_profile_id: int
    root_folder: str
    folder_name: str | None = None


class EpisodeResponse(BaseModel):
    id: int
    episode_number: int
    title: str | None
    air_date: date | None
    monitored: bool
    file_path: str | None
    file_quality: str | None

    model_config = {"from_attributes": True}


class SeasonResponse(BaseModel):
    id: int
    season_number: int
    monitored: bool
    episodes: list[EpisodeResponse] = []

    model_config = {"from_attributes": True}


class SeriesResponse(BaseModel):
    id: int
    title: str
    sort_title: str
    year: int
    tvdb_id: int
    tmdb_id: int | None
    imdb_id: str | None
    overview: str | None
    poster_url: str | None
    status: str
    series_type: str
    quality_profile_id: int
    root_folder: str
    folder_name: str
    added_at: datetime
    seasons: list[SeasonResponse] = []

    model_config = {"from_attributes": True}
