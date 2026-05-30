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


@pytest.mark.asyncio
async def test_resolve_daily_limit_falls_back_to_db(db):
    """F-13：Redis 无 daily_limit 缓存时，enforcement 应回源 DB 权威值，而非退 DEFAULT。

    根因（审计 P1-3）：_check_quota 原本 Redis 未命中即用 DEFAULT，
    忽略 admin 在 DB 设的配额，与 /profile/token-quota（读 DB）不一致。
    """
    import uuid as _uuid

    from app.core.redis import get_redis
    from app.llm.client import llm_client
    from app.models.user_quota import UserQuota
    from tests.conftest import TestSessionLocal

    uid = _uuid.uuid4()
    db.add(UserQuota(user_id=uid, daily_token_limit=100))
    await db.commit()

    r = await get_redis()
    await r.delete(f"quota:{uid}:daily_limit")  # 确保 Redis 未命中
    try:
        limit = await llm_client._resolve_daily_limit(
            str(uid), session_factory=TestSessionLocal
        )
        assert limit == 100, "Redis 未命中应回源 DB 权威值 100，而非 DEFAULT"
    finally:
        await r.delete(f"quota:{uid}:daily_limit")
