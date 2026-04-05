"""Torznab client — speaks the Torznab API protocol used by Jackett, Prowlarr, etc."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import httpx

from sodar.indexers.base import BaseIndexer, SearchResult

log = logging.getLogger(__name__)

# Torznab XML namespace
TORZNAB_NS = "http://torznab.com/schemas/2015/feed"
ATOM_NS = "http://www.w3.org/2005/Atom"


def _parse_search_results(xml_text: str, indexer_name: str) -> list[SearchResult]:
    """Parse Torznab XML search response into SearchResult objects."""
    root = ET.fromstring(xml_text)

    results = []
    for item in root.iter("item"):
        title = item.findtext("title", "")
        if not title:
            continue

        # Get download URL — prefer enclosure, fall back to link
        enclosure = item.find("enclosure")
        if enclosure is not None:
            download_url = enclosure.get("url", "")
            size = int(enclosure.get("length", "0"))
        else:
            download_url = item.findtext("link", "")
            size = 0

        info_url = item.findtext("comments") or item.findtext("guid")

        # Extract torznab attributes
        attrs = {}
        for attr in item.findall(f"{{{TORZNAB_NS}}}attr"):
            attrs[attr.get("name", "")] = attr.get("value", "")

        seeders = int(attrs["seeders"]) if "seeders" in attrs else None
        leechers = int(attrs["peers"]) - seeders if "peers" in attrs and seeders is not None else None

        if size == 0 and "size" in attrs:
            size = int(attrs["size"])

        categories = []
        for cat in item.findall("category"):
            if cat.text:
                categories.append(cat.text)
        if "category" in attrs:
            categories.append(attrs["category"])

        results.append(SearchResult(
            title=title,
            download_url=download_url,
            info_url=info_url,
            size=size,
            seeders=seeders,
            leechers=leechers,
            indexer_name=indexer_name,
            categories=categories,
        ))

    return results


class TorznabClient(BaseIndexer):
    def __init__(self, name: str, base_url: str, api_key: str, categories: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.categories = categories
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _request(self, params: dict) -> str:
        """Make a request to the Torznab API."""
        params["apikey"] = self.api_key
        url = f"{self.base_url}/api"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.text

    async def search(self, query: str, categories: list[str] | None = None) -> list[SearchResult]:
        params: dict = {"t": "search", "q": query}

        cats = categories or (self.categories.split(",") if self.categories else [])
        cats = [c.strip() for c in cats if c.strip()]
        if cats:
            params["cat"] = ",".join(cats)

        try:
            xml = await self._request(params)
            return _parse_search_results(xml, self.name)
        except Exception:
            log.exception("Torznab search failed for %s", self.name)
            return []

    async def search_movie(self, query: str, imdb_id: str | None = None) -> list[SearchResult]:
        params: dict = {"t": "movie", "q": query}
        if imdb_id:
            params["imdbid"] = imdb_id.replace("tt", "")

        cats = self.categories.split(",") if self.categories else ["2000"]
        params["cat"] = ",".join(c.strip() for c in cats if c.strip())

        try:
            xml = await self._request(params)
            return _parse_search_results(xml, self.name)
        except Exception:
            log.exception("Torznab movie search failed for %s", self.name)
            return []

    async def search_tv(
        self, query: str, season: int | None = None, episode: int | None = None, tvdb_id: int | None = None,
    ) -> list[SearchResult]:
        params: dict = {"t": "tvsearch", "q": query}
        if season is not None:
            params["season"] = str(season)
        if episode is not None:
            params["ep"] = str(episode)
        if tvdb_id is not None:
            params["tvdbid"] = str(tvdb_id)

        cats = self.categories.split(",") if self.categories else ["5000"]
        params["cat"] = ",".join(c.strip() for c in cats if c.strip())

        try:
            xml = await self._request(params)
            return _parse_search_results(xml, self.name)
        except Exception:
            log.exception("Torznab TV search failed for %s", self.name)
            return []

    async def test_connection(self) -> bool:
        try:
            xml = await self._request({"t": "caps"})
            root = ET.fromstring(xml)
            return root.tag == "caps"
        except Exception:
            log.exception("Torznab connection test failed for %s", self.name)
            return False

    async def get_capabilities(self) -> dict:
        try:
            xml = await self._request({"t": "caps"})
            root = ET.fromstring(xml)

            caps: dict = {"categories": [], "searching": {}}

            for cat in root.iter("category"):
                caps["categories"].append({
                    "id": cat.get("id", ""),
                    "name": cat.get("name", ""),
                })

            searching = root.find("searching")
            if searching is not None:
                for search_type in searching:
                    caps["searching"][search_type.tag] = {
                        "available": search_type.get("available", "no"),
                        "supportedParams": search_type.get("supportedParams", ""),
                    }

            return caps
        except Exception:
            log.exception("Failed to get capabilities for %s", self.name)
            return {}

    async def close(self):
        await self._client.aclose()
