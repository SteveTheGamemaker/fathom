"""Tests for Phase 7: additional clients, notification config, Docker wiring."""

import pytest
from dataclasses import dataclass


@dataclass
class FakeClient:
    type: str = "qbittorrent"
    host: str = "localhost"
    port: int = 8080
    username: str | None = None
    password: str | None = None
    api_key: str | None = None
    use_ssl: bool = False
    category: str | None = None


def test_make_downloader_qbittorrent():
    from fathom.downloaders import make_downloader
    dl = make_downloader(FakeClient(type="qbittorrent"))
    assert dl is not None
    assert "QBittorrent" in type(dl).__name__


def test_make_downloader_transmission():
    from fathom.downloaders import make_downloader
    dl = make_downloader(FakeClient(type="transmission"))
    assert dl is not None
    assert "Transmission" in type(dl).__name__


def test_make_downloader_sabnzbd():
    from fathom.downloaders import make_downloader
    dl = make_downloader(FakeClient(type="sabnzbd", api_key="abc123"))
    assert dl is not None
    assert "SABnzbd" in type(dl).__name__


def test_make_downloader_unknown():
    from fathom.downloaders import make_downloader
    dl = make_downloader(FakeClient(type="foobar"))
    assert dl is None


def test_notification_config():
    from fathom.config import NotificationConfig
    cfg = NotificationConfig()
    assert cfg.webhook_url == ""
    assert cfg.on_grab is True
    assert cfg.on_import is True


@pytest.mark.asyncio
async def test_web_pages_200(client):
    for path in ["/", "/movies", "/series", "/search", "/queue", "/settings"]:
        resp = await client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
