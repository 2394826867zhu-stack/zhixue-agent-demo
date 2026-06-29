"""审计(2026-06-29)回归：每日任务 new_lesson 的 source_ref_kind 正确标注。

项目树节点任务与官方课程章节任务的 source_ref_id 指向不同表，前端据 source_ref_kind
选择建会话入参——标错会导致项目节点任务点「开始」404（真机审计实测命中）。
"""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.user import User
from app.models.task import DailyTask
from app.models.project import Project, ProjectTreeNode
from app.services.task_service import task_service


@pytest.mark.asyncio
async def test_serialize_ref_kind_tree_node_vs_chapter(client, db):
    r = await client.post("/v1/auth/register",
                          json={"email": "refkind@test.com", "password": "password123"})
    uid = (await db.execute(select(User.id).where(User.email == "refkind@test.com"))).scalar_one()

    proj = Project(user_id=uid, name="P", source="user_project", subject="数学")
    db.add(proj)
    await db.flush()
    node = ProjectTreeNode(project_id=proj.id, depth=2, title="节点课时",
                           difficulty="blue", status="available", kp_id=None)
    db.add(node)
    await db.flush()

    # 一个指向项目树节点、一个指向不存在的"章节"id（模拟官方章节，非 tree_node）
    chapter_like = uuid.uuid4()
    t_node = DailyTask(user_id=uid, task_date=date.today(), title="继续学习·节点课时",
                       task_type="new_lesson", source_ref_id=node.id)
    t_chap = DailyTask(user_id=uid, task_date=date.today(), title="开始学习·官方章节",
                       task_type="new_lesson", source_ref_id=chapter_like)
    t_other = DailyTask(user_id=uid, task_date=date.today(), title="复习闪卡",
                        task_type="flashcard_review", source_ref_id=uuid.uuid4())
    db.add_all([t_node, t_chap, t_other])
    await db.commit()

    out = await task_service.serialize_with_ref_kind(db, [t_node, t_chap, t_other])
    kinds = {o.title: o.source_ref_kind for o in out}
    assert kinds["继续学习·节点课时"] == "tree_node"
    assert kinds["开始学习·官方章节"] == "chapter"
    # 非 new_lesson 任务不标注
    assert kinds["复习闪卡"] is None
