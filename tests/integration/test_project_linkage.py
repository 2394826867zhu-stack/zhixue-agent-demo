"""D-17 项目 ↔ Flashcard ↔ Mistake 三向联动：闪卡/错题列表按 project_id 过滤。

project_id 列早在 v0.23 (migration 020) 就加到 flashcards / training_questions，
但列表端点一直没暴露过滤参数。D-17 补上 GET /v1/flashcards?project_id= 与
GET /v1/mistakes?project_id=（镜像既有 subject 过滤）。
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.flashcard import Flashcard
from app.models.training import TrainingQuestion


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_flashcards_and_mistakes_filtered_by_project(client: AsyncClient, db: AsyncSession):
    email = "linkage@zhiyao.ai"
    h = await _auth(client, email)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()

    proj_a = (await client.post("/v1/projects", headers=h, json={"name": "项目A"})).json()["data"]["id"]
    proj_b = (await client.post("/v1/projects", headers=h, json={"name": "项目B"})).json()["data"]["id"]
    kp = (await client.post("/v1/knowledge-points", headers=h, json={"name": "联动KP", "subject": "数学"})).json()["data"]["id"]

    kid = uuid.UUID(kp)
    # 闪卡：A、B 各一张
    db.add(Flashcard(user_id=user.id, knowledge_point_id=kid, card_type="concept",
                     front="卡A", back="b", project_id=uuid.UUID(proj_a)))
    db.add(Flashcard(user_id=user.id, knowledge_point_id=kid, card_type="concept",
                     front="卡B", back="b", project_id=uuid.UUID(proj_b)))
    # 错题（TrainingQuestion is_wrong=True）：A、B 各一道
    for label, pid in (("题A", proj_a), ("题B", proj_b)):
        db.add(TrainingQuestion(
            user_id=user.id, knowledge_point_id=kid, bloom_level="remember",
            question_type="choice", question_text=label, reference_answer="ans",
            is_wrong=True, is_retry=False, project_id=uuid.UUID(pid),
            answered_at=datetime.now(timezone.utc),
        ))
    await db.commit()

    # 闪卡按项目 A 过滤 → 仅 1 张
    rf = await client.get(f"/v1/flashcards?project_id={proj_a}", headers=h)
    assert rf.status_code == 200, rf.text
    f_items = rf.json()["data"]["items"]
    assert len(f_items) == 1
    assert f_items[0]["front"] == "卡A"

    # 错题按项目 A 过滤 → 仅 1 道
    rm = await client.get(f"/v1/mistakes?project_id={proj_a}", headers=h)
    assert rm.status_code == 200, rm.text
    assert len(rm.json()["data"]["items"]) == 1

    # 无过滤 → 闪卡 2 张
    rall = await client.get("/v1/flashcards", headers=h)
    assert len(rall.json()["data"]["items"]) == 2
