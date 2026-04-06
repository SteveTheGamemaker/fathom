from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fathom.database import get_db_session
from fathom.models.quality import QualityProfile, QualityProfileItem
from fathom.schemas.quality import (
    QualityProfileCreate,
    QualityProfileResponse,
    QualityProfileUpdate,
)

router = APIRouter(prefix="/quality-profile", tags=["quality"])


@router.get("", response_model=list[QualityProfileResponse])
async def list_profiles(session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(QualityProfile).options(selectinload(QualityProfile.items))
    )
    return result.scalars().all()


@router.get("/{profile_id}", response_model=QualityProfileResponse)
async def get_profile(profile_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile_id)
        .options(selectinload(QualityProfile.items))
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(404, "Quality profile not found")
    return profile


@router.post("", response_model=QualityProfileResponse, status_code=201)
async def create_profile(
    data: QualityProfileCreate,
    session: AsyncSession = Depends(get_db_session),
):
    profile = QualityProfile(name=data.name, cutoff=data.cutoff)
    session.add(profile)
    await session.flush()
    for item_data in data.items:
        item = QualityProfileItem(
            profile_id=profile.id,
            **item_data.model_dump(),
        )
        session.add(item)
    await session.flush()
    # Re-fetch with items loaded
    result = await session.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile.id)
        .options(selectinload(QualityProfile.items))
    )
    return result.scalars().first()


@router.put("/{profile_id}", response_model=QualityProfileResponse)
async def update_profile(
    profile_id: int,
    data: QualityProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile_id)
        .options(selectinload(QualityProfile.items))
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(404, "Quality profile not found")

    if data.name is not None:
        profile.name = data.name
    if data.cutoff is not None:
        profile.cutoff = data.cutoff

    if data.items is not None:
        # Replace all items
        for old in profile.items:
            await session.delete(old)
        await session.flush()
        for item_data in data.items:
            item = QualityProfileItem(
                profile_id=profile.id,
                **item_data.model_dump(),
            )
            session.add(item)
        await session.flush()

    # Re-fetch
    result = await session.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile.id)
        .options(selectinload(QualityProfile.items))
    )
    return result.scalars().first()


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: int, session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(QualityProfile)
        .where(QualityProfile.id == profile_id)
        .options(selectinload(QualityProfile.items))
    )
    profile = result.scalars().first()
    if not profile:
        raise HTTPException(404, "Quality profile not found")
    await session.delete(profile)
