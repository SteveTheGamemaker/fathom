"""SABnzbd API client for NZB downloads."""

from __future__ import annotations

import logging

import httpx

from fathom.downloaders.base import BaseDownloader, TorrentStatus

log = logging.getLogger(__name__)


class SABnzbdClient(BaseDownloader):
    def __init__(
        self,
        host: str,
        port: int,
        api_key: str,
        use_ssl: bool = False,
        category: str | None = None,
    ):
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}/sabnzbd/api"
        self.api_key = api_key
        self.category = category
        self._client = httpx.AsyncClient(timeout=15.0)

    async def _api(self, mode: str, extra: dict | None = None) -> dict:
        params = {"apikey": self.api_key, "mode": mode, "output": "json"}
        if extra:
            params.update(extra)
        resp = await self._client.get(self.base_url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def test_connection(self) -> bool:
        try:
            result = await self._api("version")
            return "version" in result
        except Exception:
            log.exception("SABnzbd connection test failed")
            return False

    async def add_torrent(self, url: str, category: str | None = None) -> str | None:
        log.warning("SABnzbd does not support torrent downloads")
        return None

    async def add_nzb(self, url: str, category: str | None = None) -> str | None:
        try:
            params: dict = {"name": url}
            cat = category or self.category
            if cat:
                params["cat"] = cat
            result = await self._api("addurl", params)
            # SABnzbd returns {"status": True, "nzo_ids": ["SABnzbd_nzo_xxx"]}
            nzo_ids = result.get("nzo_ids", [])
            if nzo_ids:
                return nzo_ids[0]
            if result.get("status"):
                return None  # added but no ID returned
            log.warning("SABnzbd add NZB failed: %s", result)
            return None
        except Exception:
            log.exception("SABnzbd add NZB error")
            return None

    def _parse_slot(self, slot: dict, is_history: bool = False) -> TorrentStatus:
        if is_history:
            # History items
            status_map = {"Completed": "completed", "Failed": "error"}
            status = status_map.get(slot.get("status", ""), "completed")
            return TorrentStatus(
                download_id=slot.get("nzo_id", ""),
                name=slot.get("name", ""),
                progress=1.0 if status == "completed" else 0.0,
                size=int(slot.get("bytes", 0)),
                download_speed=0,
                upload_speed=0,
                status=status,
                save_path=slot.get("storage", slot.get("path", "")),
                eta=None,
            )
        else:
            # Queue items
            pct = float(slot.get("percentage", "0")) / 100.0
            status = "downloading" if slot.get("status") == "Downloading" else "paused"
            timeleft = slot.get("timeleft", "0:00:00")
            # Parse HH:MM:SS to seconds
            eta = None
            try:
                parts = timeleft.split(":")
                eta = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, IndexError):
                pass

            return TorrentStatus(
                download_id=slot.get("nzo_id", ""),
                name=slot.get("filename", ""),
                progress=pct,
                size=int(float(slot.get("mb", "0")) * 1024 * 1024),
                download_speed=int(float(slot.get("mbleft", "0")) * 1024 * 1024),
                upload_speed=0,
                status=status,
                save_path="",
                eta=eta,
            )

    async def get_status(self, download_id: str) -> TorrentStatus | None:
        try:
            # Check queue first
            queue = await self._api("queue")
            for slot in queue.get("queue", {}).get("slots", []):
                if slot.get("nzo_id") == download_id:
                    return self._parse_slot(slot, is_history=False)

            # Check history
            history = await self._api("history", {"limit": 50})
            for slot in history.get("history", {}).get("slots", []):
                if slot.get("nzo_id") == download_id:
                    return self._parse_slot(slot, is_history=True)

            return None
        except Exception:
            log.exception("SABnzbd get_status error")
            return None

    async def get_all(self) -> list[TorrentStatus]:
        try:
            items = []
            queue = await self._api("queue")
            for slot in queue.get("queue", {}).get("slots", []):
                items.append(self._parse_slot(slot, is_history=False))

            history = await self._api("history", {"limit": 20})
            for slot in history.get("history", {}).get("slots", []):
                items.append(self._parse_slot(slot, is_history=True))

            return items
        except Exception:
            log.exception("SABnzbd get_all error")
            return []

    async def remove(self, download_id: str, delete_files: bool = False) -> bool:
        try:
            # Try removing from queue
            result = await self._api("queue", {"name": "delete", "value": download_id})
            if result.get("status"):
                return True
            # Try removing from history
            result = await self._api("history", {"name": "delete", "value": download_id, "del_files": int(delete_files)})
            return result.get("status", False)
        except Exception:
            log.exception("SABnzbd remove error")
            return False

    async def close(self):
        await self._client.aclose()
