"""Batch release name parser — orchestrates the full pipeline:

    1. DB parse cache (free, instant — deduplicates repeated names)
    2. LLM batch parse (primary parser)
    3. Regex fallback (only when LLM is unavailable or fails)

Returns a dict mapping raw_title -> parsed result dict for every input.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from fathom.config import settings
from fathom.llm import cache, fallback
from fathom.llm.client import chat_json
from fathom.llm.prompts import build_parse_system_prompt, build_parse_user_prompt

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


def _regex_fallback_batch(release_names: list[str]) -> dict[str, dict]:
    """Last resort — parse with regex when LLM is unavailable."""
    results = {}
    for name in release_names:
        fb = fallback.try_parse(name)
        if fb is not None:
            d = _fallback_to_dict(name, fb)
            d["parse_method"] = "regex_fallback"
            results[name] = d
        else:
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

    # Step 1: DB cache lookup
    cached = await cache.lookup(session, release_names)
    remaining = []
    for name in release_names:
        if name in cached:
            results[name] = _cached_to_dict(cached[name])
        else:
            remaining.append(name)

    log.info("Cache: %d hits, %d remaining", len(cached), len(remaining))

    if not remaining:
        return results

    # Step 2: LLM batch parse (primary)
    if settings.llm.api_key or settings.llm.base_url:
        batch_size = settings.llm.max_batch_size
        llm_failed = []

        for i in range(0, len(remaining), batch_size):
            batch = remaining[i : i + batch_size]
            llm_results = await _llm_batch_parse(batch)

            if llm_results:
                await cache.store(session, llm_results, parse_method="llm")
                for r in llm_results:
                    r["parse_method"] = "llm"
                    results[r["raw_title"]] = r

            # Track any names the LLM didn't return results for
            parsed_names = {r["raw_title"] for r in llm_results}
            for name in batch:
                if name not in parsed_names:
                    llm_failed.append(name)

        remaining = llm_failed
        if not remaining:
            return results

        log.warning("LLM failed to parse %d releases, falling back to regex", len(remaining))
    else:
        log.warning("No LLM API key configured, using regex fallback for %d releases", len(remaining))

    # Step 3: Regex fallback (when LLM is unavailable or failed)
    fb_results = _regex_fallback_batch(remaining)
    results.update(fb_results)

    # Cache the regex results too
    cacheable = [r for r in fb_results.values() if r["parse_method"] == "regex_fallback"]
    if cacheable:
        await cache.store(session, cacheable, parse_method="regex_fallback")

    return results
