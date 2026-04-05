"""Tests for the quality matcher."""

from dataclasses import dataclass

from sodar.llm.matcher import rank_releases


@dataclass
class FakeItem:
    quality_name: str
    allowed: bool
    sort_order: int


@dataclass
class FakeProfile:
    name: str
    cutoff: str
    items: list


def _make_profile(name="Test", cutoff="bluray-1080p", items=None):
    if items is None:
        items = [
            ("hdtv-720p", True, 1),
            ("webdl-720p", True, 2),
            ("bluray-720p", True, 3),
            ("hdtv-1080p", True, 4),
            ("webdl-1080p", True, 5),
            ("bluray-1080p", True, 6),
            ("remux-1080p", True, 7),
        ]
    return FakeProfile(
        name=name,
        cutoff=cutoff,
        items=[FakeItem(q, a, s) for q, a, s in items],
    )


def test_ranks_by_quality():
    profile = _make_profile()
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "hdtv-720p"},
        {"raw_title": "b", "title": "Movie", "quality": "bluray-1080p"},
        {"raw_title": "c", "title": "Movie", "quality": "webdl-1080p"},
    ]
    results = rank_releases(releases, profile)
    assert len(results) == 3
    assert results[0].quality == "bluray-1080p"
    assert results[1].quality == "webdl-1080p"
    assert results[2].quality == "hdtv-720p"


def test_filters_disallowed_quality():
    profile = _make_profile(items=[
        ("hdtv-720p", False, 1),
        ("webdl-1080p", True, 5),
        ("bluray-1080p", True, 6),
    ])
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "hdtv-720p"},
        {"raw_title": "b", "title": "Movie", "quality": "webdl-1080p"},
    ]
    results = rank_releases(releases, profile)
    assert len(results) == 1
    assert results[0].quality == "webdl-1080p"


def test_filters_unknown_quality():
    profile = _make_profile()
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "unknown"},
        {"raw_title": "b", "title": "Movie", "quality": "bluray-1080p"},
    ]
    results = rank_releases(releases, profile)
    assert len(results) == 1
    assert results[0].quality == "bluray-1080p"


def test_upgrade_logic():
    profile = _make_profile()
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "hdtv-720p"},
        {"raw_title": "b", "title": "Movie", "quality": "bluray-1080p"},
        {"raw_title": "c", "title": "Movie", "quality": "remux-1080p"},
    ]
    results = rank_releases(releases, profile, current_quality="webdl-1080p")
    assert len(results) == 2
    assert results[0].quality == "remux-1080p"
    assert results[1].quality == "bluray-1080p"


def test_cutoff_reached_no_upgrades():
    profile = _make_profile()
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "hdtv-720p"},
        {"raw_title": "b", "title": "Movie", "quality": "webdl-1080p"},
    ]
    results = rank_releases(releases, profile, current_quality="bluray-1080p")
    assert len(results) == 0


def test_proper_preferred():
    profile = _make_profile()
    releases = [
        {"raw_title": "a", "title": "Movie", "quality": "bluray-1080p", "is_proper": False},
        {"raw_title": "b", "title": "Movie", "quality": "bluray-1080p", "is_proper": True},
    ]
    results = rank_releases(releases, profile)
    assert results[0].raw_title == "b"
