from __future__ import annotations

from pydantic import BaseModel


class QualityProfileItemResponse(BaseModel):
    id: int
    quality_name: str
    allowed: bool
    sort_order: int

    model_config = {"from_attributes": True}


class QualityProfileResponse(BaseModel):
    id: int
    name: str
    cutoff: str
    items: list[QualityProfileItemResponse] = []

    model_config = {"from_attributes": True}


class QualityProfileItemCreate(BaseModel):
    quality_name: str
    allowed: bool = True
    sort_order: int


class QualityProfileCreate(BaseModel):
    name: str
    cutoff: str
    items: list[QualityProfileItemCreate]


class QualityProfileUpdate(BaseModel):
    name: str | None = None
    cutoff: str | None = None
    items: list[QualityProfileItemCreate] | None = None
