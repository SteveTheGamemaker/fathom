"""qBittorrent WebUI API client."""

from __future__ import annotations

import logging

import httpx

from sodar.downloaders.base import BaseDownloader, TorrentStatus

log = logging.getLogger(__name__)


class QBittorrentClient(BaseDownloader):
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"
        self.username = username or ""
        self.password = password or ""
        self._client = httpx.AsyncClient(timeout=15.0)
        self._authenticated = False

    async def _login(self) -> bool:
        if self._authenticated:
            return True
        try:
            resp = await self._client.post(
                f"{self.base_url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
            )
            if resp.status_code == 200 and resp.text == "Ok.":
                self._authenticated = True
                return True
            log.warning("qBittorrent login failed: %s", resp.text)
            return False
        except Exception:
            log.exception("qBittorrent login error")
            return False

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        await self._login()
        return await self._client.get(f"{self.base_url}{path}", params=params)

    async def _post(self, path: str, data: dict | None = None) -> httpx.Response:
        await self._login()
        return await self._client.post(f"{self.base_url}{path}", data=data)

    async def test_connection(self) -> bool:
        try:
            if not await self._login():
                return False
            resp = await self._get("/api/v2/app/version")
            return resp.status_code == 200
        except Exception:
            log.exception("qBittorrent connection test failed")
            return False

    async def add_torrent(self, url: str, category: str | None = None) -> str | None:
        try:
            data: dict = {"urls": url}
            if category:
                data["category"] = category
            resp = await self._post("/api/v2/torrents/add", data=data)
            if resp.status_code == 200 and resp.text == "Ok.":
                # qBit doesn't return the hash directly from add.
                # For magnets, we can extract it from the URL.
                # For .torrent URLs, we'd need to poll. Return None for now
                # and let the caller match by name.
                if "magnet:" in url:
                    # Extract hash from magnet link
                    import re
                    match = re.search(r"btih:([a-fA-F0-9]{40})", url)
                    if match:
                        return match.group(1).lower()
                return None
            log.warning("qBittorrent add torrent failed: %s", resp.text)
            return None
        except Exception:
            log.exception("qBittorrent add torrent error")
            return None

    async def add_nzb(self, url: str, category: str | None = None) -> str | None:
        log.warning("qBittorrent does not support NZB downloads")
        return None

    def _parse_torrent(self, t: dict) -> TorrentStatus:
        state = t.get("state", "unknown")
        status_map = {
            "downloading": "downloading",
            "stalledDL": "downloading",
            "metaDL": "downloading",
            "forcedDL": "downloading",
            "uploading": "seeding",
            "stalledUP": "seeding",
            "forcedUP": "seeding",
            "pausedDL": "paused",
            "pausedUP": "completed",
            "queuedDL": "downloading",
            "queuedUP": "seeding",
            "checkingDL": "downloading",
            "checkingUP": "seeding",
            "error": "error",
            "missingFiles": "error",
        }
        return TorrentStatus(
            download_id=t.get("hash", ""),
            name=t.get("name", ""),
            progress=t.get("progress", 0.0),
            size=t.get("total_size", 0),
            download_speed=t.get("dlspeed", 0),
            upload_speed=t.get("upspeed", 0),
            status=status_map.get(state, "downloading"),
            save_path=t.get("save_path", t.get("content_path", "")),
            eta=t.get("eta") if t.get("eta", 8640000) < 8640000 else None,
        )

    async def get_status(self, download_id: str) -> TorrentStatus | None:
        try:
            resp = await self._get("/api/v2/torrents/info", params={"hashes": download_id})
            if resp.status_code != 200:
                return None
            torrents = resp.json()
            if not torrents:
                return None
            return self._parse_torrent(torrents[0])
        except Exception:
            log.exception("qBittorrent get_status error")
            return None

    async def get_all(self) -> list[TorrentStatus]:
        try:
            resp = await self._get("/api/v2/torrents/info")
            if resp.status_code != 200:
                return []
            return [self._parse_torrent(t) for t in resp.json()]
        except Exception:
            log.exception("qBittorrent get_all error")
            return []

    async def remove(self, download_id: str, delete_files: bool = False) -> bool:
        try:
            resp = await self._post("/api/v2/torrents/delete", data={
                "hashes": download_id,
                "deleteFiles": str(delete_files).lower(),
            })
            return resp.status_code == 200
        except Exception:
            log.exception("qBittorrent remove error")
            return False

    async def close(self):
        await self._client.aclose()
