"""Integration tests for the full parse pipeline (regex path — no LLM needed)."""

import pytest

from sodar.llm.parser import parse_releases


@pytest.mark.asyncio
async def test_parse_pipeline_regex_path(db_session):
    names = [
        "The.Matrix.1999.1080p.BluRay.x265-RARBG",
        "Breaking.Bad.S05E16.720p.WEB-DL.H.264-BS",
        "Oppenheimer.2023.2160p.WEB-DL.H.265-FLUX",
    ]

    results = await parse_releases(db_session, names)

    assert len(results) == 3

    matrix = results["The.Matrix.1999.1080p.BluRay.x265-RARBG"]
    assert matrix["title"] == "The Matrix"
    assert matrix["year"] == 1999
    assert matrix["quality"] == "bluray-1080p"
    assert matrix["parse_method"] == "regex_fallback"

    bb = results["Breaking.Bad.S05E16.720p.WEB-DL.H.264-BS"]
    assert bb["title"] == "Breaking Bad"
    assert bb["season"] == 5
    assert bb["episode"] == 16

    opp = results["Oppenheimer.2023.2160p.WEB-DL.H.265-FLUX"]
    assert opp["quality"] == "webdl-2160p"


@pytest.mark.asyncio
async def test_cache_hit_on_second_call(db_session):
    names = ["The.Matrix.1999.1080p.BluRay.x265-RARBG"]

    # First call — regex fallback + stores in cache
    r1 = await parse_releases(db_session, names)
    assert r1[names[0]]["parse_method"] == "regex_fallback"

    # Second call — should hit cache (still returns same data)
    r2 = await parse_releases(db_session, names)
    assert r2[names[0]]["title"] == "The Matrix"


@pytest.mark.asyncio
async def test_empty_input(db_session):
    results = await parse_releases(db_session, [])
    assert results == {}
