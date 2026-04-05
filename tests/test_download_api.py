"""Tests for download client CRUD, grab, and queue APIs."""

import pytest


@pytest.mark.asyncio
async def test_download_client_crud(client):
    # Create
    resp = await client.post("/api/v1/download-client", json={
        "name": "My qBit",
        "type": "qbittorrent",
        "host": "localhost",
        "port": 8080,
        "username": "admin",
        "password": "adminadmin",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My qBit"
    assert data["type"] == "qbittorrent"
    client_id = data["id"]

    # List
    resp = await client.get("/api/v1/download-client")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Update
    resp = await client.put(f"/api/v1/download-client/{client_id}", json={
        "name": "Updated qBit",
        "category": "sodar",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated qBit"
    assert resp.json()["category"] == "sodar"

    # Delete
    resp = await client.delete(f"/api/v1/download-client/{client_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_grab_no_client(client):
    resp = await client.post("/api/v1/grab", json={
        "download_url": "magnet:?xt=urn:btih:abc123",
        "release_title": "Test.Release.1080p",
    })
    assert resp.status_code == 400  # no download client configured


@pytest.mark.asyncio
async def test_queue_empty(client):
    resp = await client.get("/api/v1/queue")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_history_empty(client):
    resp = await client.get("/api/v1/history")
    assert resp.status_code == 200
    assert resp.json() == []
