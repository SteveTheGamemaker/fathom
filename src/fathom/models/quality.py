from __future__ import annotations

from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fathom.models.base import Base


class QualityProfile(Base):
    __tablename__ = "quality_profiles"

    name: Mapped[str] = mapped_column(String)
    cutoff: Mapped[str] = mapped_column(String)  # quality name to stop upgrading at
    preferred_source: Mapped[str] = mapped_column(String, default="any", server_default="any")
    # "any" = prefer physical (bluray/remux) over web, current default behaviour
    # "web" = prefer web sources (webdl/webrip) over bluray/remux at the same resolution

    items: Mapped[list[QualityProfileItem]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="QualityProfileItem.sort_order",
    )


class QualityProfileItem(Base):
    __tablename__ = "quality_profile_items"

    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("quality_profiles.id"))
    quality_name: Mapped[str] = mapped_column(String)  # e.g. "bluray-1080p"
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer)  # higher = more preferred

    profile: Mapped[QualityProfile] = relationship(back_populates="items")


# Default quality profiles to seed on first run
DEFAULT_PROFILES = [
    {
        "name": "Any",
        "cutoff": "bluray-2160p",
        "items": [
            {"quality_name": "sdtv", "allowed": True, "sort_order": 1},
            {"quality_name": "dvd", "allowed": True, "sort_order": 2},
            {"quality_name": "webdl-480p", "allowed": True, "sort_order": 3},
            {"quality_name": "webrip-480p", "allowed": True, "sort_order": 4},
            {"quality_name": "hdtv-720p", "allowed": True, "sort_order": 5},
            {"quality_name": "webdl-720p", "allowed": True, "sort_order": 6},
            {"quality_name": "webrip-720p", "allowed": True, "sort_order": 7},
            {"quality_name": "bluray-720p", "allowed": True, "sort_order": 8},
            {"quality_name": "hdtv-1080p", "allowed": True, "sort_order": 9},
            {"quality_name": "webdl-1080p", "allowed": True, "sort_order": 10},
            {"quality_name": "webrip-1080p", "allowed": True, "sort_order": 11},
            {"quality_name": "bluray-1080p", "allowed": True, "sort_order": 12},
            {"quality_name": "remux-1080p", "allowed": True, "sort_order": 13},
            {"quality_name": "webdl-2160p", "allowed": True, "sort_order": 14},
            {"quality_name": "webrip-2160p", "allowed": True, "sort_order": 15},
            {"quality_name": "bluray-2160p", "allowed": True, "sort_order": 16},
            {"quality_name": "remux-2160p", "allowed": True, "sort_order": 17},
        ],
    },
    {
        "name": "HD-720p/1080p",
        "cutoff": "bluray-1080p",
        "items": [
            {"quality_name": "hdtv-720p", "allowed": True, "sort_order": 1},
            {"quality_name": "webdl-720p", "allowed": True, "sort_order": 2},
            {"quality_name": "webrip-720p", "allowed": True, "sort_order": 3},
            {"quality_name": "bluray-720p", "allowed": True, "sort_order": 4},
            {"quality_name": "hdtv-1080p", "allowed": True, "sort_order": 5},
            {"quality_name": "webdl-1080p", "allowed": True, "sort_order": 6},
            {"quality_name": "webrip-1080p", "allowed": True, "sort_order": 7},
            {"quality_name": "bluray-1080p", "allowed": True, "sort_order": 8},
            {"quality_name": "remux-1080p", "allowed": True, "sort_order": 9},
        ],
    },
    {
        "name": "Ultra-HD",
        "cutoff": "bluray-2160p",
        "items": [
            {"quality_name": "webdl-2160p", "allowed": True, "sort_order": 1},
            {"quality_name": "webrip-2160p", "allowed": True, "sort_order": 2},
            {"quality_name": "bluray-2160p", "allowed": True, "sort_order": 3},
            {"quality_name": "remux-2160p", "allowed": True, "sort_order": 4},
        ],
    },
    {
        "name": "HD-720p",
        "cutoff": "bluray-720p",
        "items": [
            {"quality_name": "hdtv-720p", "allowed": True, "sort_order": 1},
            {"quality_name": "webdl-720p", "allowed": True, "sort_order": 2},
            {"quality_name": "webrip-720p", "allowed": True, "sort_order": 3},
            {"quality_name": "bluray-720p", "allowed": True, "sort_order": 4},
        ],
    },
    {
        "name": "HD-1080p",
        "cutoff": "bluray-1080p",
        "items": [
            {"quality_name": "hdtv-1080p", "allowed": True, "sort_order": 1},
            {"quality_name": "webdl-1080p", "allowed": True, "sort_order": 2},
            {"quality_name": "webrip-1080p", "allowed": True, "sort_order": 3},
            {"quality_name": "bluray-1080p", "allowed": True, "sort_order": 4},
            {"quality_name": "remux-1080p", "allowed": True, "sort_order": 5},
        ],
    },
]
