"""Transmission RPC client."""

from __future__ import annotations

import logging

import httpx

from sodar.downloaders.base import BaseDownloader, TorrentStatus

log = logging.getLogger(__name__)

# Transmission RPC uses a CSRF-like session ID header
SESSION_HEADER = "X-Transmission-Session-Id"


class TransmissionClient(BaseDownloader):
    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ):
        scheme = "https" if use_ssl else "http"
        self.rpc_url = f"{scheme}://{host}:{port}/transmission/rpc"
        auth = (username, password) if username else None
        self._client = httpx.AsyncClient(timeout=15.0, auth=auth)
        self._session_id: str | None = None

    async def _rpc(self, method: str, arguments: dict | None = None) -> dict:
        """Make a Transmission RPC call, handling the session-id handshake."""
        payload = {"method": method}
        if arguments:
            payload["arguments"] = arguments

        headers = {}
        if self._session_id:
            headers[SESSION_HEADER] = self._session_id

        resp = await self._client.post(self.rpc_url, json=payload, headers=headers)

        # Transmission returns 409 with a session ID on first request
        if resp.status_code == 409:
            self._session_id = resp.headers.get(SESSION_HEADER, "")
            headers[SESSION_HEADER] = self._session_id
            resp = await self._client.post(self.rpc_url, json=payload, headers=headers)

        resp.raise_for_status()
        return resp.json()

    async def test_connection(self) -> bool:
        try:
            result = await self._rpc("session-get")
            return result.get("result") == "success"
        except Exception:
            log.exception("Transmission connection test failed")
            return False

    async def add_torrent(self, url: str, category: str | None = None) -> str | None:
        try:
            args: dict = {"filename": url, "paused": False}
            if category:
                args["download-dir"] = category  # Transmission uses download-dir, not categories
            result = await self._rpc("torrent-add", args)
            if result.get("result") != "success":
                log.warning("Transmission add torrent failed: %s", result)
                return None
            torrent = result.get("arguments", {})
            # Could be "torrent-added" or "torrent-duplicate"
            added = torrent.get("torrent-added") or torrent.get("torrent-duplicate") or {}
            return added.get("hashString")
        except Exception:
            log.exception("Transmission add torrent error")
            return None

    async def add_nzb(self, url: str, category: str | None = None) -> str | None:
        log.warning("Transmission does not support NZB downloads")
        return None

    def _parse_torrent(self, t: dict) -> TorrentStatus:
        status_val = t.get("status", 0)
        # Transmission status codes: 0=stopped, 1=check_wait, 2=checking,
        # 3=download_wait, 4=downloading, 5=seed_wait, 6=seeding
        status_map = {
            0: "paused",
            1: "downloading",
            2: "downloading",
            3: "downloading",
            4: "downloading",
            5: "seeding",
            6: "seeding",
        }
        status = status_map.get(status_val, "downloading")

        # Check if error
        if t.get("error", 0) > 0:
            status = "error"

        total = t.get("totalSize", 0) or t.get("sizeWhenDone", 0)
        done = t.get("percentDone", 0)
        if done >= 1.0 and status != "error":
            status = "completed" if status_val == 0 else status

        return TorrentStatus(
            download_id=t.get("hashString", ""),
            name=t.get("name", ""),
            progress=done,
            size=total,
            download_speed=t.get("rateDownload", 0),
            upload_speed=t.get("rateUpload", 0),
            status=status,
            save_path=t.get("downloadDir", ""),
            eta=t.get("eta") if t.get("eta", -1) >= 0 else None,
        )

    async def get_status(self, download_id: str) -> TorrentStatus | None:
        try:
            result = await self._rpc("torrent-get", {
                "ids": [download_id],
                "fields": [
                    "hashString", "name", "percentDone", "totalSize", "sizeWhenDone",
                    "rateDownload", "rateUpload", "status", "downloadDir", "eta", "error",
                ],
            })
            torrents = result.get("arguments", {}).get("torrents", [])
            if not torrents:
                return None
            return self._parse_torrent(torrents[0])
        except Exception:
            log.exception("Transmission get_status error")
            return None

    async def get_all(self) -> list[TorrentStatus]:
        try:
            result = await self._rpc("torrent-get", {
                "fields": [
                    "hashString", "name", "percentDone", "totalSize", "sizeWhenDone",
                    "rateDownload", "rateUpload", "status", "downloadDir", "eta", "error",
                ],
            })
            torrents = result.get("arguments", {}).get("torrents", [])
            return [self._parse_torrent(t) for t in torrents]
        except Exception:
            log.exception("Transmission get_all error")
            return []

    async def remove(self, download_id: str, delete_files: bool = False) -> bool:
        try:
            result = await self._rpc("torrent-remove", {
                "ids": [download_id],
                "delete-local-data": delete_files,
            })
            return result.get("result") == "success"
        except Exception:
            log.exception("Transmission remove error")
            return False

    async def close(self):
        await self._client.aclose()
