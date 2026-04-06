from __future__ import annotations

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    categories: list[str] | None = None
    indexer_ids: list[int] | None = None  # None = search all enabled


class SearchResultItem(BaseModel):
    # From indexer
    title: str
    download_url: str
    info_url: str | None
    size: int
    seeders: int | None
    leechers: int | None
    indexer_name: str
    # From parser
    parsed_title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    quality: str = "unknown"
    codec: str | None = None
    source: str | None = None
    resolution: str | None = None
    release_group: str | None = None
    is_proper: bool = False
    is_repack: bool = False
    parse_method: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
