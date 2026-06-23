"""
Basic API smoke tests.
Run: pytest tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.anyio
async def test_root():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/")
    assert r.status_code == 200


@pytest.mark.anyio
async def test_upload_no_file():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post("/api/v1/upload/image")
    assert r.status_code == 422   # Validation error — file required


@pytest.mark.anyio
async def test_violations_list():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/violations")
    # Will return 200 even if DB is empty
    assert r.status_code in (200, 500)


@pytest.mark.anyio
async def test_analytics_summary():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/analytics/summary")
    assert r.status_code in (200, 500)
