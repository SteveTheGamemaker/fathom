"""Regex-based fast-path parser for common release name patterns.

Handles ~60% of releases with zero LLM cost. If any key field is ambiguous,
returns None so the release gets sent to the LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- Patterns ---

RE_RESOLUTION = re.compile(r"\b(2160|1080|720|480)[pi]\b", re.IGNORECASE)

RE_SOURCE = re.compile(
    r"\b(Blu-?Ray|BDRip|BD|REMUX|WEB-DL|WEBDL|WEBRip|WEB|HDTV|DVDRip|DVD|PDTV|SDTV)\b",
    re.IGNORECASE,
)

RE_CODEC = re.compile(
    r"\b([xXhH]\.?26[45]|HEVC|AV1|AVC|MPEG-?2|VC-?1|10bit)\b",
    re.IGNORECASE,
)

RE_SEASON_EPISODE = re.compile(r"\bS(\d{1,3})E(\d{1,3})\b", re.IGNORECASE)
RE_SEASON_ONLY = re.compile(r"\bS(\d{1,3})\b(?!E\d)", re.IGNORECASE)

RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

RE_GROUP = re.compile(r"-([A-Za-z0-9]+)(?:\[.*\])?$")

RE_PROPER = re.compile(r"\bPROPER\b", re.IGNORECASE)
RE_REPACK = re.compile(r"\bREPACK\b", re.IGNORECASE)

# Tokens that mark the end of the title portion
_TITLE_STOP_TOKENS = re.compile(
    r"\b("
    r"2160p|1080p|720p|480p|"
    r"Blu-?Ray|BDRip|REMUX|WEB-DL|WEBDL|WEBRip|HDTV|DVDRip|DVD|PDTV|SDTV|"
    r"[xXhH]\.?264|[xXhH]\.?265|HEVC|AV1|AVC|"
    r"PROPER|REPACK|RERIP|"
    r"DTS|DD[P57]|AAC|FLAC|Atmos|TrueHD|"
    r"S\d{1,3}E\d{1,3}|S\d{1,3}"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class FallbackResult:
    title: str
    year: int | None
    season: int | None
    episode: int | None
    quality: str
    codec: str | None
    source: str | None
    resolution: str | None
    release_group: str | None
    is_proper: bool
    is_repack: bool


_SOURCE_MAP = {
    "bluray": "bluray",
    "blu-ray": "bluray",
    "bdrip": "bluray",
    "bd": "bluray",
    "remux": "remux",
    "web-dl": "webdl",
    "webdl": "webdl",
    "web": "webdl",
    "webrip": "webrip",
    "hdtv": "hdtv",
    "pdtv": "hdtv",
    "sdtv": "hdtv",
    "dvdrip": "dvd",
    "dvd": "dvd",
}

_CODEC_MAP = {
    "x264": "h264",
    "h264": "h264",
    "h.264": "h264",
    "x.264": "h264",
    "avc": "h264",
    "x265": "h265",
    "h265": "h265",
    "h.265": "h265",
    "x.265": "h265",
    "hevc": "h265",
    "av1": "av1",
    "mpeg2": "mpeg2",
    "mpeg-2": "mpeg2",
    "vc1": "vc1",
    "vc-1": "vc1",
    "10bit": None,  # modifier, not a codec
}


def _normalize_source(raw: str) -> str:
    return _SOURCE_MAP.get(raw.lower(), raw.lower())


def _normalize_codec(raw: str) -> str | None:
    return _CODEC_MAP.get(raw.lower().replace(".", ""), raw.lower())


def _derive_quality(source: str | None, resolution: str | None) -> str:
    if not resolution and not source:
        return "unknown"

    res = resolution or ""
    src = source or ""

    if src == "remux":
        if res == "2160p":
            return "remux-2160p"
        return "remux-1080p"

    if src == "bluray":
        if res == "2160p":
            return "bluray-2160p"
        if res == "720p":
            return "bluray-720p"
        return "bluray-1080p"

    if src in ("webdl", "web"):
        if res == "2160p":
            return "webdl-2160p"
        if res == "1080p":
            return "webdl-1080p"
        if res == "480p":
            return "webdl-480p"
        return "webdl-720p"

    if src == "webrip":
        if res == "2160p":
            return "webrip-2160p"
        if res == "1080p":
            return "webrip-1080p"
        if res == "480p":
            return "webrip-480p"
        return "webrip-720p"

    if src == "hdtv":
        if res == "1080p":
            return "hdtv-1080p"
        if res in ("720p", "1080p"):
            return "hdtv-720p"
        return "hdtv-720p"

    if src == "dvd":
        return "dvd"

    # Have resolution but unknown source
    if res == "2160p":
        return "webdl-2160p"
    if res == "1080p":
        return "webdl-1080p"
    if res == "720p":
        return "webdl-720p"
    if res == "480p":
        return "webdl-480p"

    return "unknown"


def _extract_title(name: str, year_match: re.Match | None) -> str:
    """Extract the title from the release name.

    The title is everything before the first quality/source/resolution/episode token
    or the year (whichever comes first), with dots and underscores replaced by spaces.
    """
    # Find the earliest "stop" token
    stop = _TITLE_STOP_TOKENS.search(name)
    stop_pos = stop.start() if stop else len(name)

    # Year also acts as a title boundary (title comes before it)
    if year_match and year_match.start() < stop_pos:
        raw = name[: year_match.start()]
    else:
        raw = name[:stop_pos]

    # Clean up
    title = raw.replace(".", " ").replace("_", " ").strip(" -")

    return title.strip()


def try_parse(release_name: str) -> FallbackResult | None:
    """Attempt to parse a release name using regex patterns.

    Returns a FallbackResult if we can confidently extract the key fields,
    or None if the LLM should handle this one.
    """
    name = release_name.strip()

    # Extract fields
    res_match = RE_RESOLUTION.search(name)
    src_match = RE_SOURCE.search(name)
    codec_match = RE_CODEC.search(name)
    se_match = RE_SEASON_EPISODE.search(name)
    s_match = RE_SEASON_ONLY.search(name) if not se_match else None
    year_match = RE_YEAR.search(name)
    group_match = RE_GROUP.search(name)

    resolution = (res_match.group(0).lower() if res_match else None)
    source = (_normalize_source(src_match.group(1)) if src_match else None)
    codec = (_normalize_codec(codec_match.group(1)) if codec_match else None)

    # We need at least resolution OR source to have confidence
    if not resolution and not source:
        return None

    title = _extract_title(name, year_match)
    if not title or len(title) < 2:
        return None

    quality = _derive_quality(source, resolution)

    return FallbackResult(
        title=title,
        year=int(year_match.group(1)) if year_match else None,
        season=int(se_match.group(1)) if se_match else (int(s_match.group(1)) if s_match else None),
        episode=int(se_match.group(2)) if se_match else None,
        quality=quality,
        codec=codec,
        source=source,
        resolution=resolution,
        release_group=group_match.group(1) if group_match else None,
        is_proper=bool(RE_PROPER.search(name)),
        is_repack=bool(RE_REPACK.search(name)),
    )
