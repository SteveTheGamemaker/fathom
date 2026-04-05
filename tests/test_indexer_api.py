"""Tests for indexer CRUD API and search endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from sodar.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_indexer_crud(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        resp = await client.post("/api/v1/indexer", json={
            "name": "Test Jackett",
            "type": "torznab",
            "base_url": "http://localhost:9117/api/v1/indexers/test",
            "api_key": "abc123",
            "categories": "2000,5000",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Jackett"
        assert data["api_key"] == "abc123"
        indexer_id = data["id"]

        # List
        resp = await client.get("/api/v1/indexer")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # Get
        resp = await client.get(f"/api/v1/indexer/{indexer_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Jackett"

        # Update
        resp = await client.put(f"/api/v1/indexer/{indexer_id}", json={
            "name": "Updated Jackett",
            "priority": 10,
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Jackett"
        assert resp.json()["priority"] == 10

        # Delete
        resp = await client.delete(f"/api/v1/indexer/{indexer_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = await client.get(f"/api/v1/indexer/{indexer_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_no_indexers(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/search", json={"query": "The Matrix"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []
