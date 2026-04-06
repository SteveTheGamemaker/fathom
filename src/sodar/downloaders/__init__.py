"""Download client factory."""

from __future__ import annotations

from sodar.downloaders.base import BaseDownloader
from sodar.models.download import DownloadClient


def make_downloader(client: DownloadClient) -> BaseDownloader | None:
    """Create the appropriate downloader instance from a DownloadClient DB record."""
    if client.type == "qbittorrent":
        from sodar.downloaders.qbittorrent import QBittorrentClient
        return QBittorrentClient(
            host=client.host, port=client.port,
            username=client.username, password=client.password,
            use_ssl=client.use_ssl,
        )
    elif client.type == "transmission":
        from sodar.downloaders.transmission import TransmissionClient
        return TransmissionClient(
            host=client.host, port=client.port,
            username=client.username, password=client.password,
            use_ssl=client.use_ssl,
        )
    elif client.type == "sabnzbd":
        from sodar.downloaders.sabnzbd import SABnzbdClient
        return SABnzbdClient(
            host=client.host, port=client.port,
            api_key=client.api_key or "",
            use_ssl=client.use_ssl,
            category=client.category,
        )
    return None
