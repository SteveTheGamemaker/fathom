from __future__ import annotations

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from sodar.models.base import Base


class Indexer(Base):
    __tablename__ = "indexers"

    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="torznab")  # torznab | newznab
    base_url: Mapped[str] = mapped_column(String)
    api_key: Mapped[str] = mapped_column(String, default="")
    categories: Mapped[str] = mapped_column(String, default="")  # comma-separated IDs
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)  # lower = searched first
