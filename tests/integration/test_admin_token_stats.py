"""admin Token 用量统计 · GET /admin/tokens/stats 带真实数据。

回归：admin_service.get_token_stats 的 by_model/top_users 聚合用 .label("t")/.label("c")，
与 SQLAlchemy 2.0 保留的已弃用 Row.t/.c 属性同名 → r.t 返回 Row 而非求和值，有数据即 500。
既有 smoke 测试用空库（聚合为空，comprehension 不执行）从未触发。此测种真实 token_usage 锁住。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.token_usage import TokenUsage


async def _admin_token(client, monkeypatch) -> str:
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "tokstats-setup", raising=False)
    await client.post("/admin/auth/setup", json={
        "email": "tokstats_admin@zhiyao.com", "password": "admin_pw_123456",
        "secret_key": "tokstats-setup",
    })
    r = await client.post("/admin/auth/login", json={
        "email": "tokstats_admin@zhiyao.com", "password": "admin_pw_123456",
    })
    return r.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_token_stats_with_real_usage(client: AsyncClient, db, monkeypatch):
    await client.post("/v1/auth/register", json={"email": "tok_u@zhiyao.ai", "password": "password123"})
    uid = (await db.execute(select(User.id).where(User.email == "tok_u@zhiyao.ai"))).scalar_one()

    db.add_all([
        TokenUsage(user_id=uid, model="deepseek-v4-flash", endpoint="agent",
                   prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0012),
        TokenUsage(user_id=uid, model="deepseek-v4-flash", endpoint="note",
                   prompt_tokens=200, completion_tokens=80, total_tokens=280, cost_usd=0.0021),
        TokenUsage(user_id=uid, model="gpt-4o", endpoint="agent",
                   prompt_tokens=300, completion_tokens=100, total_tokens=400, cost_usd=0.02),
    ])
    await db.commit()

    token = await _admin_token(client, monkeypatch)
    resp = await client.get("/admin/tokens/stats?days=7", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text  # 此前真实数据下 500
    data = resp.json()["data"]

    assert data["total_calls"] == 3
    assert data["total_tokens"] == 830
    by_model = {m["model"]: m for m in data["by_model"]}
    assert by_model["deepseek-v4-flash"]["total_tokens"] == 430  # 150+280
    assert by_model["gpt-4o"]["total_tokens"] == 400
    assert data["top_users"][0]["total_tokens"] == 830
    assert data["top_users"][0]["email"] == "tok_u@zhiyao.ai"
