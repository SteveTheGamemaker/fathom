"""Batch release name parser — orchestrates the full pipeline:

    1. Regex fallback (free, instant)
    2. DB parse cache (free, fast)
    3. LLM batch parse (paid, smart)

Returns a dict mapping raw_title -> parsed result dict for every input.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from sodar.config import settings
from sodar.llm import cache, fallback
from sodar.llm.client import chat_json
from sodar.llm.prompts import build_parse_system_prompt, build_parse_user_prompt

log = logging.getLogger(__name__)


def _fallback_to_dict(raw_title: str, result: fallback.FallbackResult) -> dict:
    d = asdict(result)
    d["raw_title"] = raw_title
    return d


def _cached_to_dict(record) -> dict:
    return {
        "raw_title": record.raw_title,
        "title": record.parsed_title,
        "year": record.year,
        "season": record.season,
        "episode": record.episode,
        "quality": record.quality,
        "codec": record.codec,
        "source": record.source,
        "resolution": record.resolution,
        "release_group": record.release_group,
        "is_proper": record.is_proper,
        "is_repack": record.is_repack,
        "parse_method": record.parse_method,
    }


async def _llm_batch_parse(release_names: list[str]) -> list[dict]:
    """Send a batch of release names to the LLM for parsing."""
    system = build_parse_system_prompt()
    user = build_parse_user_prompt(release_names)

    try:
        response = await chat_json(system=system, user=user)
    except Exception:
        log.exception("LLM parse failed for batch of %d releases", len(release_names))
        return []

    releases = response.get("releases", [])
    if not isinstance(releases, list):
        log.warning("LLM returned unexpected format: %s", type(releases))
        return []

    # Zip results back to their original names
    parsed = []
    for i, name in enumerate(release_names):
        if i < len(releases):
            r = releases[i]
            r["raw_title"] = name
            r.setdefault("quality", "unknown")
            r.setdefault("is_proper", False)
            r.setdefault("is_repack", False)
            parsed.append(r)
        else:
            log.warning("LLM returned fewer results than expected (%d < %d)", len(releases), len(release_names))
            break

    return parsed


async def parse_releases(
    session: AsyncSession,
    release_names: list[str],
) -> dict[str, dict]:
    """Parse a batch of release names through the full pipeline.

    Returns a dict mapping raw_title -> parsed result dict.
    """
    if not release_names:
        return {}

    results: dict[str, dict] = {}
    remaining: list[str] = []

    # Step 1: Regex fallback
    regex_results = []
    for name in release_names:
        fb = fallback.try_parse(name)
        if fb is not None:
            d = _fallback_to_dict(name, fb)
            d["parse_method"] = "regex_fallback"
            results[name] = d
            regex_results.append(d)
        else:
            remaining.append(name)

    log.info(
        "Regex fallback: %d/%d parsed, %d remaining",
        len(regex_results), len(release_names), len(remaining),
    )

    # Store regex results in cache
    if regex_results:
        await cache.store(session, regex_results, parse_method="regex_fallback")

    if not remaining:
        return results

    # Step 2: DB cache lookup
    cached = await cache.lookup(session, remaining)
    for name in list(remaining):
        if name in cached:
            results[name] = _cached_to_dict(cached[name])
            remaining.remove(name)

    log.info(
        "Cache hits: %d, still remaining: %d",
        len(cached), len(remaining),
    )

    if not remaining:
        return results

    # Step 3: LLM batch parse
    if not settings.llm.api_key:
        log.warning("No LLM API key configured — %d releases left unparsed", len(remaining))
        for name in remaining:
            results[name] = {
                "raw_title": name,
                "title": name,
                "year": None,
                "season": None,
                "episode": None,
                "quality": "unknown",
                "codec": None,
                "source": None,
                "resolution": None,
                "release_group": None,
                "is_proper": False,
                "is_repack": False,
                "parse_method": "unparsed",
            }
        return results

    # Batch in chunks
    batch_size = settings.llm.max_batch_size
    for i in range(0, len(remaining), batch_size):
        batch = remaining[i : i + batch_size]
        llm_results = await _llm_batch_parse(batch)

        # Store in cache
        if llm_results:
            await cache.store(session, llm_results, parse_method="llm")

        for r in llm_results:
            r["parse_method"] = "llm"
            results[r["raw_title"]] = r

    # Any names that the LLM didn't return results for
    for name in remaining:
        if name not in results:
            results[name] = {
                "raw_title": name,
                "title": name,
                "year": None,
                "season": None,
                "episode": None,
                "quality": "unknown",
                "codec": None,
                "source": None,
                "resolution": None,
                "release_group": None,
                "is_proper": False,
                "is_repack": False,
                "parse_method": "failed",
            }

    return results
