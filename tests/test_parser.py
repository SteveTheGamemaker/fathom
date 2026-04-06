"""Integration tests for the parse pipeline."""

import pytest

from fathom.llm.parser import parse_releases


@pytest.mark.asyncio
async def test_parse_pipeline(db_session):
    names = [
        "The.Matrix.1999.1080p.BluRay.x265-RARBG",
        "Breaking.Bad.S05E16.720p.WEB-DL.H.264-BS",
        "Oppenheimer.2023.2160p.WEB-DL.H.265-FLUX",
    ]

    results = await parse_releases(db_session, names)
    assert len(results) == 3

    matrix = results["The.Matrix.1999.1080p.BluRay.x265-RARBG"]
    assert "Matrix" in matrix["title"]
    assert matrix["year"] == 1999
    assert "1080" in matrix["quality"]

    bb = results["Breaking.Bad.S05E16.720p.WEB-DL.H.264-BS"]
    assert bb["season"] == 5
    assert bb["episode"] == 16

    opp = results["Oppenheimer.2023.2160p.WEB-DL.H.265-FLUX"]
    assert "2160" in opp["quality"]


@pytest.mark.asyncio
async def test_cache_hit_on_second_call(db_session):
    names = ["The.Matrix.1999.1080p.BluRay.x265-RARBG"]

    r1 = await parse_releases(db_session, names)
    assert "Matrix" in r1[names[0]]["title"]

    # Second call — should hit cache and return same data
    r2 = await parse_releases(db_session, names)
    assert r2[names[0]]["title"] == r1[names[0]]["title"]


@pytest.mark.asyncio
async def test_empty_input(db_session):
    results = await parse_releases(db_session, [])
    assert results == {}
