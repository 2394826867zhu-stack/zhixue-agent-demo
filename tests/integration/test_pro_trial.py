"""E-04 · 7 天 Pro 免费试用端到端测试。"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_trial_requires_auth(client: AsyncClient):
    resp = await client.post("/v1/subscription/trial")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_status_shows_trial_available_for_free_user(client: AsyncClient):
    token = await _register(client, "trial_avail@zhiyao.ai")
    resp = await client.get("/v1/subscription/status", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()["data"]
    assert data["plan_type"] == "free"
    assert data["is_pro"] is False
    assert data["trial_available"] is True
    assert data["is_trial"] is False


@pytest.mark.asyncio
async def test_start_trial_grants_pro_for_7_days(client: AsyncClient):
    token = await _register(client, "trial_start@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/v1/subscription/trial", headers=H)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["plan_type"] == "pro"
    assert data["is_pro"] is True
    assert data["is_trial"] is True
    assert data["trial_available"] is False
    # 7 天试用：days_remaining 6 或 7（取决于 timedelta.days 截断）
    assert data["days_remaining"] in (6, 7)
    assert data["features"]["unlimited_agent"] is True


@pytest.mark.asyncio
async def test_trial_only_once(client: AsyncClient):
    token = await _register(client, "trial_once@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}

    assert (await client.post("/v1/subscription/trial", headers=H)).status_code == 200
    # 第二次：拒绝
    resp = await client.post("/v1/subscription/trial", headers=H)
    assert resp.status_code == 400
    assert "试用" in resp.json()["message"]


@pytest.mark.asyncio
async def test_trial_rejected_for_existing_pro(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "trial_pro@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    # 手动置为 edu（永久 Pro）
    me = (await db.execute(select(User).where(User.email == "trial_pro@zhiyao.ai"))).scalar_one()
    me.plan_type = "edu"
    await db.commit()

    resp = await client.post("/v1/subscription/trial", headers=H)
    assert resp.status_code == 400
    assert "Pro" in resp.json()["message"]


@pytest.mark.asyncio
async def test_trial_persists_and_records_event(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "trial_persist@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    await client.post("/v1/subscription/trial", headers=H)

    me = (await db.execute(select(User).where(User.email == "trial_persist@zhiyao.ai"))).scalar_one()
    assert me.trial_used is True
    assert me.trial_ends_at is not None
    assert me.plan_type == "pro"
