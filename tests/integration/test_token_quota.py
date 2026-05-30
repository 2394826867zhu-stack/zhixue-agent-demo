"""F-10 用户 token 配额查询端点 GET /v1/profile/token-quota。

让前端在昂贵 LLM 调用前先查余量。必须与 enforcement（llm/client._check_quota）
读同一真相源：limit=DB 权威值（无则 DEFAULT），used=Redis quota:{uid}:used:{today}。
"""
from datetime import date

import pytest
from httpx import AsyncClient

from app.config import settings


async def _auth(client: AsyncClient, email: str) -> tuple[dict, str]:
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    me = await client.get("/v1/auth/me", headers=h)
    return h, me.json()["data"]["id"]


@pytest.mark.asyncio
async def test_token_quota_default_for_new_user(client: AsyncClient):
    h, _ = await _auth(client, "quota_default@zhiyao.ai")
    resp = await client.get("/v1/profile/token-quota", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["daily_limit"] == settings.DEFAULT_DAILY_TOKEN_LIMIT
    assert data["used"] == 0, "新用户今日未消耗"
    assert data["remaining"] == settings.DEFAULT_DAILY_TOKEN_LIMIT
    assert data["is_default_limit"] is True
    assert data["date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_token_quota_reflects_redis_usage(client: AsyncClient):
    """验证 used 读的是 enforcement 真实 Redis 源，而非 hardcode。"""
    from app.core.redis import get_redis

    h, uid = await _auth(client, "quota_used@zhiyao.ai")
    today = date.today().isoformat()
    r = await get_redis()
    key = f"quota:{uid}:used:{today}"
    await r.set(key, 5000)
    try:
        resp = await client.get("/v1/profile/token-quota", headers=h)
        data = resp.json()["data"]
        assert data["used"] == 5000
        assert data["remaining"] == data["daily_limit"] - 5000
    finally:
        await r.delete(key)
