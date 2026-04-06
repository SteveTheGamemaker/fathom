from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fathom.database import get_db_session
from fathom.models.media import Movie, Series, Season, Episode, MediaStatus
from fathom.schemas.media import (
    MovieCreate,
    MovieResponse,
    SeriesCreate,
    SeriesResponse,
)

router = APIRouter(tags=["media"])


def _sort_title(title: str) -> str:
    """Generate a sort-friendly title (lowercase, strip leading articles)."""
    t = title.lower().strip()
    for article in ("the ", "a ", "an "):
        if t.startswith(article):
            t = t[len(article):]
            break
    return t


def _default_folder(title: str, year: int) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    return f"{safe} ({year})"


# --- Movies ---

@router.get("/movie", response_model=list[MovieResponse])
async def list_movies(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Movie).order_by(Movie.sort_title))
    return result.scalars().all()


@router.post("/movie", response_model=MovieResponse, status_code=201)
async def add_movie(data: MovieCreate, session: AsyncSession = Depends(get_db_session)):
    # Check for duplicate
    existing = await session.execute(select(Movie).where(Movie.tmdb_id == data.tmdb_id))
    if existing.scalars().first():
        raise HTTPException(409, "Movie already exists")

    folder = data.folder_name or _default_folder(data.title, data.year)
    movie = Movie(
        title=data.title,
        sort_title=_sort_title(data.title),
        year=data.year,
        tmdb_id=data.tmdb_id,
        imdb_id=data.imdb_id,
        overview=data.overview,
        poster_url=data.poster_url,
        quality_profile_id=data.quality_profile_id,
        root_folder=data.root_folder,
        folder_name=folder,
    )
    session.add(movie)
    await session.flush()
    await session.refresh(movie)
    return movie


@router.get("/movie/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: int, session: AsyncSession = Depends(get_db_session)):
    movie = await session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")
    return movie


@router.delete("/movie/{movie_id}", status_code=204)
async def delete_movie(movie_id: int, session: AsyncSession = Depends(get_db_session)):
    movie = await session.get(Movie, movie_id)
    if not movie:
        raise HTTPException(404, "Movie not found")
    await session.delete(movie)


# --- Series ---

@router.get("/series", response_model=list[SeriesResponse])
async def list_series(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Series)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
        .order_by(Series.sort_title)
    )
    return result.scalars().all()


@router.post("/series", response_model=SeriesResponse, status_code=201)
async def add_series(data: SeriesCreate, session: AsyncSession = Depends(get_db_session)):
    existing = await session.execute(select(Series).where(Series.tvdb_id == data.tvdb_id))
    if existing.scalars().first():
        raise HTTPException(409, "Series already exists")

    folder = data.folder_name or _default_folder(data.title, data.year)
    series = Series(
        title=data.title,
        sort_title=_sort_title(data.title),
        year=data.year,
        tvdb_id=data.tvdb_id,
        tmdb_id=data.tmdb_id,
        imdb_id=data.imdb_id,
        overview=data.overview,
        poster_url=data.poster_url,
        series_type=data.series_type,
        quality_profile_id=data.quality_profile_id,
        root_folder=data.root_folder,
        folder_name=folder,
    )
    session.add(series)
    await session.flush()

    # Re-fetch with relationships
    result = await session.execute(
        select(Series)
        .where(Series.id == series.id)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
    )
    return result.scalars().first()


@router.get("/series/{series_id}", response_model=SeriesResponse)
async def get_series(series_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Series)
        .where(Series.id == series_id)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
    )
    series = result.scalars().first()
    if not series:
        raise HTTPException(404, "Series not found")
    return series


@router.delete("/series/{series_id}", status_code=204)
async def delete_series(series_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Series)
        .where(Series.id == series_id)
        .options(selectinload(Series.seasons).selectinload(Season.episodes))
    )
    series = result.scalars().first()
    if not series:
        raise HTTPException(404, "Series not found")
    await session.delete(series)
