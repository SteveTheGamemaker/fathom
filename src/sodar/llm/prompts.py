from __future__ import annotations

QUALITY_VOCABULARY = [
    "unknown",
    "sdtv",
    "dvd",
    "webdl-480p",
    "webdl-720p",
    "webdl-1080p",
    "webdl-2160p",
    "webrip-480p",
    "webrip-720p",
    "webrip-1080p",
    "webrip-2160p",
    "hdtv-720p",
    "hdtv-1080p",
    "bluray-720p",
    "bluray-1080p",
    "bluray-2160p",
    "remux-1080p",
    "remux-2160p",
]

PARSE_SYSTEM_PROMPT = """\
You are a media release name parser. Your job is to extract structured metadata \
from torrent/usenet release names.

For each release name, extract these fields:
- title: The clean media title (no dots, underscores, or quality info). Capitalize normally.
- year: Release year (integer) if present, otherwise null.
- season: Season number (integer) if this is a TV release, otherwise null.
- episode: Episode number (integer) if this is a single episode, otherwise null. \
  Null for full season packs.
- quality: One of: {qualities}. Combine source and resolution to pick the best match. \
  Use "unknown" only if you truly cannot determine it.
- codec: One of "h264", "h265", "av1", "mpeg2", "vc1", or null if not determinable.
- source: One of "bluray", "webdl", "webrip", "hdtv", "dvd", "remux", or null.
- resolution: One of "2160p", "1080p", "720p", "480p", or null.
- release_group: The scene/P2P release group name, or null. Usually appears after a \
  hyphen at the end of the name.
- is_proper: true if the release contains PROPER in the name, otherwise false.
- is_repack: true if the release contains REPACK in the name, otherwise false.

Respond with a JSON object containing a "releases" array. Each element corresponds \
to one input release name, in order.\
"""

PARSE_USER_TEMPLATE = """\
Parse the following release names:

{numbered_releases}\
"""


def build_parse_system_prompt() -> str:
    return PARSE_SYSTEM_PROMPT.format(qualities=", ".join(QUALITY_VOCABULARY))


def build_parse_user_prompt(release_names: list[str]) -> str:
    numbered = "\n".join(f"{i+1}. \"{name}\"" for i, name in enumerate(release_names))
    return PARSE_USER_TEMPLATE.format(numbered_releases=numbered)
