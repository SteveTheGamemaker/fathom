"""Tests for media and quality profile APIs."""

import pytest


@pytest.mark.asyncio
async def test_quality_profiles_seeded(client):
    resp = await client.get("/api/v1/quality-profile")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) >= 4
    names = [p["name"] for p in profiles]
    assert "Any" in names
    assert "HD-1080p" in names


@pytest.mark.asyncio
async def test_movie_crud(client):
    # Get a quality profile
    resp = await client.get("/api/v1/quality-profile")
    profile_id = resp.json()[0]["id"]

    # Add movie
    resp = await client.post("/api/v1/movie", json={
        "title": "The Matrix",
        "year": 1999,
        "tmdb_id": 603,
        "quality_profile_id": profile_id,
        "root_folder": "/movies",
    })
    assert resp.status_code == 201
    movie = resp.json()
    assert movie["title"] == "The Matrix"
    assert movie["folder_name"] == "The Matrix (1999)"
    assert movie["status"] == "monitored"
    movie_id = movie["id"]

    # List
    resp = await client.get("/api/v1/movie")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Get
    resp = await client.get(f"/api/v1/movie/{movie_id}")
    assert resp.status_code == 200

    # Duplicate check
    resp = await client.post("/api/v1/movie", json={
        "title": "The Matrix",
        "year": 1999,
        "tmdb_id": 603,
        "quality_profile_id": profile_id,
        "root_folder": "/movies",
    })
    assert resp.status_code == 409

    # Delete
    resp = await client.delete(f"/api/v1/movie/{movie_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_series_crud(client):
    resp = await client.get("/api/v1/quality-profile")
    profile_id = resp.json()[0]["id"]

    resp = await client.post("/api/v1/series", json={
        "title": "Breaking Bad",
        "year": 2008,
        "tvdb_id": 81189,
        "quality_profile_id": profile_id,
        "root_folder": "/tv",
    })
    assert resp.status_code == 201
    series = resp.json()
    assert series["title"] == "Breaking Bad"
    assert series["folder_name"] == "Breaking Bad (2008)"
    series_id = series["id"]

    resp = await client.get(f"/api/v1/series/{series_id}")
    assert resp.status_code == 200

    resp = await client.delete(f"/api/v1/series/{series_id}")
    assert resp.status_code == 204
