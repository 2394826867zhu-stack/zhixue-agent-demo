"""审计 L1 修复回归：项目树节点气泡 course_description 真填充。

此前 project_tree_service.get_node_bubble 把 course_description 硬编码为 ""（"Agent 后续填充"
占位），使契约该字段恒为空（前端节点气泡课程描述永远空白）。修复后改为：优先取关联 KP 的
content，其次章节 lesson_title，皆无则空串。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.curriculum import CurriculumChapter
from app.models.project import ProjectTreeNode


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


async def _make_project(client: AsyncClient, h: dict) -> str:
    return (await client.post("/v1/projects", headers=h, json={"name": "树项目"})).json()["data"]["id"]


@pytest.mark.asyncio
async def test_node_bubble_course_description_from_kp(client: AsyncClient, db: AsyncSession):
    email = "treebubble-kp@zhiyao.ai"
    h = await _auth(client, email)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    proj = await _make_project(client, h)

    kp = KnowledgePoint(user_id=user.id, name="导数定义", subject="数学",
                        content="导数是函数在某点的瞬时变化率。")
    db.add(kp)
    await db.flush()
    node = ProjectTreeNode(project_id=uuid.UUID(proj), kp_id=kp.id, title="导数节点",
                           difficulty="blue", status="available", depth=2)
    db.add(node)
    await db.commit()

    r = await client.get(f"/v1/projects/{proj}/tree/nodes/{node.id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # 修复前恒为 ""；现应为 KP 的 content
    assert data["course_description"] == "导数是函数在某点的瞬时变化率。"
    assert data["course_title"] == "导数节点"


@pytest.mark.asyncio
async def test_node_bubble_course_description_from_chapter(client: AsyncClient, db: AsyncSession):
    """无 KP、有章节时回退到章节 lesson_title。"""
    email = "treebubble-ch@zhiyao.ai"
    h = await _auth(client, email)
    proj = await _make_project(client, h)

    ch = CurriculumChapter(subject="数学", grade_type="senior_high", grade_year=1, semester=1,
                           chapter_index=1, chapter_title="导数", lesson_index=1, lesson_title="导数的概念")
    db.add(ch)
    await db.flush()
    node = ProjectTreeNode(project_id=uuid.UUID(proj), curriculum_chapter_id=ch.id,
                           title="章节节点", difficulty="blue", status="available", depth=2)
    db.add(node)
    await db.commit()

    r = await client.get(f"/v1/projects/{proj}/tree/nodes/{node.id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["course_description"] == "导数的概念"
