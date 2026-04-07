"""Quality matcher — deterministic matching of parsed releases against quality profiles.

No LLM involved here. This is pure rules-based ranking.
"""

from __future__ import annotations

from dataclasses import dataclass

from fathom.models.quality import QualityProfile, QualityProfileItem

# Resolution tiers — ensures 1080p is always ranked above 720p regardless of source.
_RES_TIER: dict[str, int] = {"480p": 1, "720p": 2, "1080p": 3, "2160p": 4}

# Source ranking within a resolution tier.
# "any"  → physical sources (bluray/remux) preferred over web — current default.
# "web"  → web sources (webdl/webrip) preferred over physical.
_SOURCE_RANK: dict[str, dict[str, int]] = {
    "any": {"sdtv": 1, "dvd": 1, "hdtv": 2, "webdl": 3, "webrip": 4, "bluray": 5, "remux": 6},
    "web": {"sdtv": 1, "dvd": 1, "hdtv": 2, "bluray": 3, "remux": 4, "webdl": 5, "webrip": 6},
}


def _effective_score(quality_name: str, preferred_source: str) -> int:
    """Resolution-aware score that respects source preference.

    Scores are always higher for better resolutions (e.g. 1080p > 720p) and
    within the same resolution, source preference decides the winner.
    """
    parts = quality_name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in _RES_TIER:
        source, resolution = parts[0], parts[1]
    else:
        source, resolution = quality_name, None

    res_score = _RES_TIER.get(resolution, 0) * 10
    rank_table = _SOURCE_RANK.get(preferred_source, _SOURCE_RANK["any"])
    src_score = rank_table.get(source, 0)
    return res_score + src_score


@dataclass
class MatchResult:
    """A release candidate scored against a quality profile."""
    raw_title: str
    parsed_title: str
    quality: str
    score: int  # higher = better match within the profile
    meets_cutoff: bool  # True if this quality >= the cutoff
    is_upgrade: bool  # True if better than current file quality
    is_proper: bool
    is_repack: bool
    seeders: int | None
    size: int


def _build_quality_map(profile: QualityProfile) -> dict[str, QualityProfileItem]:
    """Build a lookup from quality_name -> item for the profile."""
    return {item.quality_name: item for item in profile.items}


def rank_releases(
    parsed_releases: list[dict],
    profile: QualityProfile,
    current_quality: str | None = None,
) -> list[MatchResult]:
    """Rank parsed releases against a quality profile.

    Args:
        parsed_releases: List of parsed release dicts (from parser.parse_releases).
        profile: The quality profile to match against.
        current_quality: The quality of the currently downloaded file, if any.

    Returns:
        Sorted list of MatchResult (best first), filtered to only allowed qualities.
    """
    quality_map = _build_quality_map(profile)

    # Find the cutoff sort_order
    cutoff_item = quality_map.get(profile.cutoff)
    cutoff_order = cutoff_item.sort_order if cutoff_item else 0

    # Find current file's sort_order
    current_item = quality_map.get(current_quality) if current_quality else None
    current_order = current_item.sort_order if current_item else 0

    results = []
    for release in parsed_releases:
        quality = release.get("quality", "unknown")
        item = quality_map.get(quality)

        # Skip if quality not in profile or not allowed
        if not item or not item.allowed:
            continue

        is_upgrade = item.sort_order > current_order
        meets_cutoff = item.sort_order >= cutoff_order

        # If we already have a file, only consider upgrades
        if current_quality and not is_upgrade:
            continue

        results.append(MatchResult(
            raw_title=release.get("raw_title", ""),
            parsed_title=release.get("title", ""),
            quality=quality,
            score=_effective_score(quality, getattr(profile, "preferred_source", "any")),
            meets_cutoff=meets_cutoff,
            is_upgrade=is_upgrade,
            is_proper=release.get("is_proper", False),
            is_repack=release.get("is_repack", False),
            seeders=release.get("seeders"),
            size=release.get("size", 0),
        ))

    # Sort: highest quality score first, then proper/repack, then most seeders
    results.sort(
        key=lambda r: (
            r.score,
            r.is_proper or r.is_repack,
            r.seeders or 0,
        ),
        reverse=True,
    )

    return results
