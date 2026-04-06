"""Parse cache — stores LLM/regex parse results keyed by raw release title.

A release name always parses to the same result, so this cache never invalidates.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from fathom.models.release import ParsedRelease

log = logging.getLogger(__name__)


async def lookup(session: AsyncSession, raw_titles: list[str]) -> dict[str, ParsedRelease]:
    """Look up cached parse results for a batch of release titles.

    Returns a dict mapping raw_title -> ParsedRelease for cache hits.
    """
    if not raw_titles:
        return {}

    stmt = select(ParsedRelease).where(ParsedRelease.raw_title.in_(raw_titles))
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return {r.raw_title: r for r in rows}


async def store(
    session: AsyncSession,
    results: list[dict],
    parse_method: str = "llm",
) -> list[ParsedRelease]:
    """Store parsed results in the cache. Skips duplicates."""
    if not results:
        return []

    # Check which ones already exist
    raw_titles = [r["raw_title"] for r in results]
    existing = await lookup(session, raw_titles)

    new_rows = []
    for r in results:
        if r["raw_title"] in existing:
            continue
        new_rows.append({
            "raw_title": r["raw_title"],
            "parsed_title": r["title"],
            "year": r.get("year"),
            "season": r.get("season"),
            "episode": r.get("episode"),
            "quality": r.get("quality", "unknown"),
            "codec": r.get("codec"),
            "source": r.get("source"),
            "resolution": r.get("resolution"),
            "release_group": r.get("release_group"),
            "is_proper": r.get("is_proper", False),
            "is_repack": r.get("is_repack", False),
            "parse_method": parse_method,
        })

    if new_rows:
        stmt = sqlite_insert(ParsedRelease).values(new_rows).on_conflict_do_nothing(
            index_elements=["raw_title"]
        )
        await session.execute(stmt)
        await session.flush()

    # Return all records (cached + newly inserted)
    all_cached = await lookup(session, raw_titles)
    return list(all_cached.values())
