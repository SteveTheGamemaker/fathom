from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sodar.database import get_db_session
from sodar.indexers.torznab import TorznabClient
from sodar.indexers.newznab import NewznabClient
from sodar.llm.parser import parse_releases
from sodar.models.indexer import Indexer
from sodar.schemas.search import SearchRequest, SearchResponse, SearchResultItem

log = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    data: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    # Get indexers to search
    stmt = select(Indexer).where(Indexer.enabled == True)
    if data.indexer_ids:
        stmt = stmt.where(Indexer.id.in_(data.indexer_ids))
    stmt = stmt.order_by(Indexer.priority)

    result = await session.execute(stmt)
    indexers = result.scalars().all()

    # Search all indexers in parallel
    async def _search_one(indexer: Indexer):
        if indexer.type == "newznab":
            client = NewznabClient(
                name=indexer.name, base_url=indexer.base_url,
                api_key=indexer.api_key, categories=indexer.categories,
            )
        else:
            client = TorznabClient(
                name=indexer.name, base_url=indexer.base_url,
                api_key=indexer.api_key, categories=indexer.categories,
            )
        try:
            return await client.search(data.query, data.categories)
        finally:
            await client.close()

    indexer_results = await asyncio.gather(
        *[_search_one(idx) for idx in indexers],
        return_exceptions=True,
    )

    # Flatten results, skip exceptions
    all_results = []
    for r in indexer_results:
        if isinstance(r, Exception):
            log.warning("Indexer search failed: %s", r)
            continue
        all_results.extend(r)

    if not all_results:
        return SearchResponse(query=data.query, total=0, results=[])

    # Parse all release names through the LLM pipeline
    release_names = [r.title for r in all_results]
    parsed = await parse_releases(session, release_names)

    # Merge indexer results with parsed data
    items = []
    for r in all_results:
        p = parsed.get(r.title, {})
        items.append(SearchResultItem(
            title=r.title,
            download_url=r.download_url,
            info_url=r.info_url,
            size=r.size,
            seeders=r.seeders,
            leechers=r.leechers,
            indexer_name=r.indexer_name,
            parsed_title=p.get("title"),
            year=p.get("year"),
            season=p.get("season"),
            episode=p.get("episode"),
            quality=p.get("quality", "unknown"),
            codec=p.get("codec"),
            source=p.get("source"),
            resolution=p.get("resolution"),
            release_group=p.get("release_group"),
            is_proper=p.get("is_proper", False),
            is_repack=p.get("is_repack", False),
            parse_method=p.get("parse_method"),
        ))

    # Sort: best quality first, then most seeders
    items.sort(key=lambda x: (x.seeders or 0), reverse=True)

    return SearchResponse(query=data.query, total=len(items), results=items)
