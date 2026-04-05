from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sodar.database import get_db_session
from sodar.indexers.torznab import TorznabClient
from sodar.models.indexer import Indexer
from sodar.schemas.indexer import IndexerCreate, IndexerResponse, IndexerUpdate

router = APIRouter(prefix="/indexer", tags=["indexers"])


def _make_client(indexer: Indexer) -> TorznabClient:
    return TorznabClient(
        name=indexer.name,
        base_url=indexer.base_url,
        api_key=indexer.api_key,
        categories=indexer.categories,
    )


@router.get("", response_model=list[IndexerResponse])
async def list_indexers(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Indexer).order_by(Indexer.priority))
    return result.scalars().all()


@router.post("", response_model=IndexerResponse, status_code=201)
async def create_indexer(
    data: IndexerCreate,
    session: AsyncSession = Depends(get_db_session),
):
    indexer = Indexer(**data.model_dump())
    session.add(indexer)
    await session.flush()
    await session.refresh(indexer)
    return indexer


@router.get("/{indexer_id}", response_model=IndexerResponse)
async def get_indexer(indexer_id: int, session: AsyncSession = Depends(get_db_session)):
    indexer = await session.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    return indexer


@router.put("/{indexer_id}", response_model=IndexerResponse)
async def update_indexer(
    indexer_id: int,
    data: IndexerUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    indexer = await session.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(indexer, key, value)
    await session.flush()
    await session.refresh(indexer)
    return indexer


@router.delete("/{indexer_id}", status_code=204)
async def delete_indexer(indexer_id: int, session: AsyncSession = Depends(get_db_session)):
    indexer = await session.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    await session.delete(indexer)


@router.post("/{indexer_id}/test")
async def test_indexer(indexer_id: int, session: AsyncSession = Depends(get_db_session)):
    indexer = await session.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    client = _make_client(indexer)
    try:
        ok = await client.test_connection()
        return {"success": ok}
    finally:
        await client.close()


@router.get("/{indexer_id}/caps")
async def indexer_capabilities(indexer_id: int, session: AsyncSession = Depends(get_db_session)):
    indexer = await session.get(Indexer, indexer_id)
    if not indexer:
        raise HTTPException(404, "Indexer not found")
    client = _make_client(indexer)
    try:
        return await client.get_capabilities()
    finally:
        await client.close()
