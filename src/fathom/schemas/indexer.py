from __future__ import annotations

from pydantic import BaseModel


class IndexerCreate(BaseModel):
    name: str
    type: str = "torznab"
    base_url: str
    api_key: str = ""
    categories: str = ""
    enabled: bool = True
    priority: int = 50


class IndexerUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    categories: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class IndexerResponse(BaseModel):
    id: int
    name: str
    type: str
    base_url: str
    api_key: str
    categories: str
    enabled: bool
    priority: int

    model_config = {"from_attributes": True}
