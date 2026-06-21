"""G1-2 章节详情端点：GET /v1/curriculum/chapters/{id}。

前端 ChapterDetailScreen 调 getChapterDetail → GET /v1/curriculum/chapters/{id}，
后端此前无此端点 → 永久 404。本测试建 chapter + 用户 + KP（部分挂章节）→ 断言
详情字段（title/subject/description/kp_count/has_note）对齐前端 ChapterDetail 契约。
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.curriculum import CurriculumChapter
from app.models.note import Note
from app.models.knowledge_point import KnowledgePoint


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _chapter(**kw) -> CurriculumChapter:
    defaults = dict(
        subject="数学", grade_type="senior_high", grade_year=2, semester=1,
        chapter_index=1, chapter_title="集合与函数", lesson_index=1,
        lesson_title="集合的概念", textbook_version="人教版A", is_key=True,
    )
    defaults.update(kw)
    return CurriculumChapter(**defaults)


@pytest.mark.asyncio
async def test_chapter_detail_returns_fields(client: AsyncClient, db: AsyncSession):
    h = await _auth(client, "chapdetail@zhiyao.ai")
    user = (await db.execute(select(User).where(User.email == "chapdetail@zhiyao.ai"))).scalar_one()

    ch = _chapter()
    db.add(ch)
    await db.commit()
    await db.refresh(ch)

    # 该用户在此课时下 2 个 KP，其中 1 个挂了 note（has_note=True）
    note = Note(user_id=user.id, title="集合笔记", subject="数学",
                source_type="ai_generated", source_input="集合", status="done")
    db.add(note)
    await db.commit()
    await db.refresh(note)
    db.add(KnowledgePoint(user_id=user.id, chapter_id=ch.id, note_id=note.id,
                          name="集合定义", subject="数学", bloom_level="remember"))
    db.add(KnowledgePoint(user_id=user.id, chapter_id=ch.id,
                          name="子集", subject="数学", bloom_level="remember"))
    await db.commit()

    r = await client.get(f"/v1/curriculum/chapters/{ch.id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == str(ch.id)
    assert data["title"] == "集合的概念"
    assert data["subject"] == "数学"
    assert data["description"] == "集合与函数"  # 用所属章节标题作描述
    assert data["kp_count"] == 2
    assert data["has_note"] is True


@pytest.mark.asyncio
async def test_chapter_detail_has_note_false_when_no_linked_note(client: AsyncClient, db: AsyncSession):
    h = await _auth(client, "chapnonote@zhiyao.ai")
    user = (await db.execute(select(User).where(User.email == "chapnonote@zhiyao.ai"))).scalar_one()

    ch = _chapter(lesson_title="函数的概念", lesson_index=2)
    db.add(ch)
    await db.commit()
    await db.refresh(ch)

    db.add(KnowledgePoint(user_id=user.id, chapter_id=ch.id,
                          name="映射", subject="数学", bloom_level="remember"))
    await db.commit()

    r = await client.get(f"/v1/curriculum/chapters/{ch.id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["kp_count"] == 1
    assert data["has_note"] is False


@pytest.mark.asyncio
async def test_chapter_detail_404_when_missing(client: AsyncClient, db: AsyncSession):
    h = await _auth(client, "chap404@zhiyao.ai")
    r = await client.get(f"/v1/curriculum/chapters/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_chapter_detail_does_not_shadow_my_kps(client: AsyncClient, db: AsyncSession):
    """路由顺序自证：/chapters/{id}/my-kps 仍走子路径，不被 /chapters/{id} 吃掉。"""
    h = await _auth(client, "chaproute@zhiyao.ai")
    ch = _chapter(lesson_title="路由课时")
    db.add(ch)
    await db.commit()
    await db.refresh(ch)

    r = await client.get(f"/v1/curriculum/chapters/{ch.id}/my-kps", headers=h)
    assert r.status_code == 200, r.text
    # my-kps 返回 KP 列表（list），详情返回 dict，结构不同 → 未串
    assert isinstance(r.json()["data"], list)
