"""G-P4-2 · 外部成绩锚端到端：录入成绩 + 相关报告。"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.exam import Exam


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _uid(db: AsyncSession, email: str) -> uuid.UUID:
    return (await db.execute(select(User).where(User.email == email))).scalar_one().id


@pytest.mark.asyncio
async def test_score_anchor_requires_auth(client: AsyncClient):
    assert (await client.get("/v1/learning/score-anchor")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_record_score_via_update_and_validation(client: AsyncClient):
    token = await _register(client, "anchor_rec@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    future = (date.today() + timedelta(days=10)).isoformat()
    eid = (await client.post("/v1/exams", headers=H, json={"name": "期中", "subject": "math", "exam_date": future})).json()["data"]["id"]

    # 录入成绩
    resp = await client.put(f"/v1/exams/{eid}", headers=H, json={"score_pct": 88.5})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["score_pct"] == pytest.approx(88.5)

    # 越界拒绝
    bad = await client.put(f"/v1/exams/{eid}", headers=H, json={"score_pct": 150})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_score_anchor_empty_is_honest(client: AsyncClient):
    token = await _register(client, "anchor_empty@zhiyao.ai")
    resp = await client.get("/v1/learning/score-anchor", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()["data"]
    assert data["n"] == 0
    assert data["correlation"] is None


@pytest.mark.asyncio
async def test_score_anchor_correlation(client: AsyncClient, db: AsyncSession):
    token = await _register(client, "anchor_corr@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    uid = await _uid(db, "anchor_corr@zhiyao.ai")

    # 三学科：掌握度高→考分高（应强正相关）
    rows = [("math", 0.9, 92.0), ("chinese", 0.6, 64.0), ("english", 0.3, 38.0)]
    for subj, mastery, score in rows:
        db.add(KnowledgePoint(user_id=uid, name=f"kp_{subj}", subject=subj, p_mastery=mastery))
        db.add(Exam(user_id=uid, name=f"{subj}考", subject=subj, exam_date=date.today(), score_pct=score))
    await db.commit()

    resp = await client.get("/v1/learning/score-anchor", headers=H)
    data = resp.json()["data"]
    assert data["n"] == 3
    assert data["correlation"] is not None
    assert data["correlation"] > 0.9
    assert data["mean_score_pct"] == pytest.approx((92 + 64 + 38) / 3)
