from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TorrentStatus:
    """Status of a torrent in the download client."""
    download_id: str  # hash or unique ID
    name: str
    progress: float  # 0.0 to 1.0
    size: int  # bytes
    download_speed: int  # bytes/sec
    upload_speed: int  # bytes/sec
    status: str  # downloading | seeding | paused | completed | error
    save_path: str
    eta: int | None  # seconds remaining, or None


class BaseDownloader(ABC):
    @abstractmethod
    async def test_connection(self) -> bool:
        ...

    @abstractmethod
    async def add_torrent(self, url: str, category: str | None = None) -> str | None:
        """Add a torrent by URL/magnet. Returns the download ID (hash) or None on failure."""
        ...

    @abstractmethod
    async def add_nzb(self, url: str, category: str | None = None) -> str | None:
        """Add an NZB by URL. Returns the download ID or None on failure."""
        ...

    @abstractmethod
    async def get_status(self, download_id: str) -> TorrentStatus | None:
        ...

    @abstractmethod
    async def get_all(self) -> list[TorrentStatus]:
        ...

    @abstractmethod
    async def remove(self, download_id: str, delete_files: bool = False) -> bool:
        ...
