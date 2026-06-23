"""admin 运维后台 · GET /admin/inbox-summary 到达通知聚合。

未处理反馈(status!=resolved) + 待客服工单(status==open) + 未解死信(resolved==False)
+ 全局当日 token 用量(Redis quota:global:used:{today}) + 全局闸上限。
"""
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.feedback import Feedback
from app.models.support import SupportThread
from app.models.dead_letter import DeadLetterTask


async def _admin_token(client, monkeypatch) -> str:
    monkeypatch.setattr(settings, "ADMIN_SETUP_TOKEN", "inbox-setup-token", raising=False)
    await client.post("/admin/auth/setup", json={
        "email": "inbox_admin@zhiyao.com", "password": "admin_pw_123456",
        "secret_key": "inbox-setup-token",
    })
    r = await client.post("/admin/auth/login", json={
        "email": "inbox_admin@zhiyao.com", "password": "admin_pw_123456",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _register_uid(client, db, email: str) -> uuid.UUID:
    await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


@pytest.mark.asyncio
async def test_inbox_summary_requires_admin(client: AsyncClient):
    assert (await client.get("/admin/inbox-summary")).status_code == 401


@pytest.mark.asyncio
async def test_inbox_summary_counts_and_global_quota(client: AsyncClient, db, monkeypatch):
    from app.core.redis import get_redis

    token = await _admin_token(client, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}
    uid = await _register_uid(client, db, "inbox_user@zhiyao.ai")

    # 反馈：open + triaged 计入未处理(2)，resolved 不计
    db.add_all([
        Feedback(user_id=uid, category="bug", content="a", status="open"),
        Feedback(user_id=uid, category="suggestion", content="b", status="triaged"),
        Feedback(user_id=uid, category="other", content="c", status="resolved"),
    ])
    # 工单：open 计入(1)，pending 不计
    db.add_all([
        SupportThread(user_id=uid, subject="s1", status="open"),
        SupportThread(user_id=uid, subject="s2", status="pending"),
    ])
    # 死信：未解(1) + 已解(不计)
    db.add_all([
        DeadLetterTask(task_name="t.fail", error="boom", resolved=False),
        DeadLetterTask(task_name="t.ok", error="boom", resolved=True),
    ])
    await db.commit()

    # 全局当日 token 用量（与 enforcement 同一 Redis 真相源）
    today = date.today().isoformat()
    gkey = f"quota:global:used:{today}"
    r = await get_redis()
    await r.set(gkey, 12345)
    try:
        resp = await client.get("/admin/inbox-summary", headers=h)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["unresolved_feedback"] == 2
        assert data["open_support_threads"] == 1
        assert data["unresolved_dead_letters"] == 1
        assert data["global_token_used_today"] == 12345
        assert data["global_token_limit"] == settings.GLOBAL_DAILY_TOKEN_LIMIT
    finally:
        await r.delete(gkey)
