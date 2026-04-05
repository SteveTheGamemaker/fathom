from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single result from an indexer search."""
    title: str
    download_url: str  # .torrent link or magnet or NZB URL
    info_url: str | None  # link to the indexer's detail page
    size: int  # bytes
    seeders: int | None
    leechers: int | None
    indexer_name: str
    categories: list[str]


class BaseIndexer(ABC):
    """Abstract interface for indexer clients."""

    @abstractmethod
    async def search(self, query: str, categories: list[str] | None = None) -> list[SearchResult]:
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        ...

    @abstractmethod
    async def get_capabilities(self) -> dict:
        ...
