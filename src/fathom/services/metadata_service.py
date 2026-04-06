"""TMDB metadata service for looking up movies and TV series."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        params["api_key"] = self.api_key
        resp = await self._client.get(f"{TMDB_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def search_movie(self, query: str, year: int | None = None) -> list[dict]:
        params: dict = {"query": query}
        if year:
            params["year"] = str(year)
        data = await self._get("/search/movie", params)
        return [
            {
                "tmdb_id": r["id"],
                "title": r["title"],
                "year": int(r["release_date"][:4]) if r.get("release_date") else None,
                "overview": r.get("overview", ""),
                "poster_url": f"{TMDB_IMAGE_BASE}{r['poster_path']}" if r.get("poster_path") else None,
            }
            for r in data.get("results", [])
        ]

    async def get_movie(self, tmdb_id: int) -> dict:
        data = await self._get(f"/movie/{tmdb_id}", {"append_to_response": "external_ids"})
        ext = data.get("external_ids", {})
        return {
            "tmdb_id": data["id"],
            "title": data["title"],
            "year": int(data["release_date"][:4]) if data.get("release_date") else None,
            "overview": data.get("overview", ""),
            "poster_url": f"{TMDB_IMAGE_BASE}{data['poster_path']}" if data.get("poster_path") else None,
            "imdb_id": ext.get("imdb_id"),
        }

    async def search_tv(self, query: str, year: int | None = None) -> list[dict]:
        params: dict = {"query": query}
        if year:
            params["first_air_date_year"] = str(year)
        data = await self._get("/search/tv", params)
        return [
            {
                "tmdb_id": r["id"],
                "title": r["name"],
                "year": int(r["first_air_date"][:4]) if r.get("first_air_date") else None,
                "overview": r.get("overview", ""),
                "poster_url": f"{TMDB_IMAGE_BASE}{r['poster_path']}" if r.get("poster_path") else None,
            }
            for r in data.get("results", [])
        ]

    async def get_tv(self, tmdb_id: int) -> dict:
        data = await self._get(f"/tv/{tmdb_id}", {"append_to_response": "external_ids"})
        ext = data.get("external_ids", {})
        seasons = []
        for s in data.get("seasons", []):
            seasons.append({
                "season_number": s["season_number"],
                "episode_count": s.get("episode_count", 0),
                "name": s.get("name", ""),
            })
        return {
            "tmdb_id": data["id"],
            "title": data["name"],
            "year": int(data["first_air_date"][:4]) if data.get("first_air_date") else None,
            "overview": data.get("overview", ""),
            "poster_url": f"{TMDB_IMAGE_BASE}{data['poster_path']}" if data.get("poster_path") else None,
            "imdb_id": ext.get("imdb_id"),
            "tvdb_id": ext.get("tvdb_id"),
            "seasons": seasons,
        }

    async def get_tv_season(self, tmdb_id: int, season_number: int) -> list[dict]:
        data = await self._get(f"/tv/{tmdb_id}/season/{season_number}")
        return [
            {
                "episode_number": ep["episode_number"],
                "title": ep.get("name"),
                "air_date": ep.get("air_date"),
                "overview": ep.get("overview", ""),
            }
            for ep in data.get("episodes", [])
        ]

    async def close(self):
        await self._client.aclose()
