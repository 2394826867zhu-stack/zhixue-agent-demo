"""D-06 · Knowledge-base API — auth-guard smoke tests."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_kb_upload_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/knowledge-base/upload")
    # HTTPBearer returns 403 when Authorization header is absent
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_kb_list_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/knowledge-base/")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_kb_delete_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/v1/knowledge-base/{uuid.uuid4()}")
    assert resp.status_code in (401, 403)
