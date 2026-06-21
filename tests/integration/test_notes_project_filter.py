"""G1-4 笔记三向联动：GET /v1/notes?project_id= 按项目过滤。

SPEC §4.2 声称 notes 列表支持 ?project_id=，但端点此前只接受 subject query。
本测试镜像 flashcards/mistakes 的 project_id 过滤，断言只返回该项目笔记。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.note import Note


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_notes_filtered_by_project(client: AsyncClient, db: AsyncSession):
    h = await _auth(client, "noteproj@zhiyao.ai")
    user = (await db.execute(select(User).where(User.email == "noteproj@zhiyao.ai"))).scalar_one()

    proj_a = (await client.post("/v1/projects", headers=h, json={"name": "项目A"})).json()["data"]["id"]
    proj_b = (await client.post("/v1/projects", headers=h, json={"name": "项目B"})).json()["data"]["id"]

    db.add(Note(user_id=user.id, title="笔记A", subject="数学", source_type="ai_generated",
                status="done", project_id=uuid.UUID(proj_a)))
    db.add(Note(user_id=user.id, title="笔记B", subject="数学", source_type="ai_generated",
                status="done", project_id=uuid.UUID(proj_b)))
    db.add(Note(user_id=user.id, title="无项目笔记", subject="数学", source_type="ai_generated",
                status="done"))
    await db.commit()

    # 按项目 A 过滤 → 仅 1 条
    ra = await client.get(f"/v1/notes?project_id={proj_a}", headers=h)
    assert ra.status_code == 200, ra.text
    items = ra.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "笔记A"

    # 无过滤 → 全部 3 条
    rall = await client.get("/v1/notes", headers=h)
    assert len(rall.json()["data"]["items"]) == 3
