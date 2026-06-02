"""G-P4-4 · 效率仪表盘端到端。"""
import uuid
import pytest
from datetime import date, datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.task import PomodoroRecord


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _uid(db: AsyncSession, email: str) -> uuid.UUID:
    return (await db.execute(select(User).where(User.email == email))).scalar_one().id


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    assert (await client.get("/v1/learning/dashboard")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_empty_keeps_honesty(client: AsyncClient):
    token = await _register(client, "dash_empty@zhiyao.ai")
    data = (await client.get("/v1/learning/dashboard", headers={"Authorization": f"Bearer {token}"})).json()["data"]
    # 无数据：增益 None，但诚实框架在场
    assert data["output_effect"]["normalized_gain"] is None
    assert "+1σ" in data["output_effect"]["honest_ceiling"]
    assert data["honesty_note"]
    assert data["external_anchor"]["n"] == 0


@pytest.mark.asyncio
async def test_dashboard_with_signals(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "dash_data@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    uid = await _uid(db, "dash_data@zhiyao.ai")

    for i, m in enumerate([0.6, 0.8, 0.7]):
        db.add(KnowledgePoint(user_id=uid, name=f"kp{i}", subject="math", p_mastery=m))
    now = datetime.now(timezone.utc)
    db.add(PomodoroRecord(user_id=uid, record_date=date.today(), duration_minutes=120,
                          started_at=now, completed_at=now))
    db.add(PomodoroRecord(user_id=uid, record_date=date.today(), duration_minutes=60,
                          started_at=now, completed_at=now))
    await db.commit()

    data = (await client.get("/v1/learning/dashboard", headers=H)).json()["data"]
    oe = data["output_effect"]
    assert oe["probed_kp_count"] == 3
    assert oe["avg_mastery_pct"] == pytest.approx((60 + 80 + 70) / 3)
    assert oe["normalized_gain"] is not None  # 平均掌握 70% > 基线 30%
    assert data["efficiency"]["focus_minutes"] == 180
    assert data["efficiency"]["mastery_gain_per_hour"] is not None
