"""StudySpace 生成式教学 · lesson_plan 字段（plan Task A2）。

知曜开场把「3-5 核心概念框架」写成结构化 lesson_plan（{steps, current_index}）
喂前端 PathStepper（「第 N/M 步」）。本测试锁住会话详情端点
`GET /v1/studyspace/sessions/{id}` 透传该字段。

复用既有集成约定：真实 `client` + `db` fixture，`/v1/auth/register` 拿 token，
ORM 直接 seed 一条 lesson session（conftest 测试库走 create_all，已含新列）。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.curriculum import CurriculumChapter
from app.models.studyspace import StudySpaceSession

pytestmark = pytest.mark.asyncio


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


async def _user_id(client: AsyncClient, token: str) -> uuid.UUID:
    resp = await client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


async def _seed_lesson_session(
    db: AsyncSession, user_id: uuid.UUID
) -> StudySpaceSession:
    chapter = CurriculumChapter(
        subject="math",
        grade_type="senior",
        grade_year=1,
        semester=1,
        chapter_index=1,
        chapter_title="导数",
        lesson_index=1,
        lesson_title="导数的定义",
    )
    db.add(chapter)
    await db.flush()

    ss = StudySpaceSession(
        user_id=user_id,
        chapter_id=chapter.id,
        session_type="lesson",
        status="active",
    )
    db.add(ss)
    await db.flush()
    return ss


async def test_session_detail_returns_lesson_plan(
    client: AsyncClient, db: AsyncSession
):
    token = await _register(client, "ss_lesson_plan@zhiyao.ai")
    uid = await _user_id(client, token)
    ss = await _seed_lesson_session(db, uid)

    ss.lesson_plan = {
        "steps": ["导数定义", "用导数判断增减", "极值点"],
        "current_index": 1,
    }
    await db.commit()

    r = await client.get(
        f"/v1/studyspace/sessions/{ss.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["lesson_plan"]["steps"][1] == "用导数判断增减"
    assert data["lesson_plan"]["current_index"] == 1


async def test_session_detail_lesson_plan_defaults_null(
    client: AsyncClient, db: AsyncSession
):
    """未设置 lesson_plan 的会话详情返回 None（nullable，不报错）。"""
    token = await _register(client, "ss_lesson_plan_null@zhiyao.ai")
    uid = await _user_id(client, token)
    ss = await _seed_lesson_session(db, uid)
    await db.commit()

    r = await client.get(
        f"/v1/studyspace/sessions/{ss.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["lesson_plan"] is None
