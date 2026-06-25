"""项目创建体系 v3 · INC-A 数据模型字段回归。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §3
- 未设 v3 字段建项目 → 全部安全默认值（存量零破坏，向后兼容铁律）。
- 显式设 v3 字段 → 原样持久化回读 + subject 两层格式容量（String(80)）。
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.models.project import Project


async def _register_uid(client: AsyncClient, db, email: str) -> uuid.UUID:
    resp = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 200, resp.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


@pytest.mark.asyncio
async def test_project_v3_fields_default(client: AsyncClient, db):
    """未设 v3 字段建项目 → 全部安全默认值（向后兼容）。"""
    uid = await _register_uid(client, db, "v3default@test.com")
    project = Project(user_id=uid, name="存量项目")
    db.add(project)
    await db.commit()
    await db.refresh(project)

    assert project.goal_type == "interest"
    assert project.goal_spec == {}
    assert project.starting_mode == "from_scratch"
    assert project.starting_payload == {}
    assert project.prior_knowledge_strategy is None
    assert project.mastery_depth is None
    assert project.scope_mode == "full_subject"
    assert project.scope_topics == []


@pytest.mark.asyncio
async def test_project_v3_fields_roundtrip(client: AsyncClient, db):
    """显式设 v3 字段 → 原样持久化回读。"""
    uid = await _register_uid(client, db, "v3roundtrip@test.com")
    project = Project(
        user_id=uid,
        name="考研数学一备考",
        subject="数理科学 > 数学",  # 两层格式，需 String(80)
        goal_type="exam",
        goal_spec={"exam_name": "考研", "exam_date": "2026-12-25", "target_score": 130},
        starting_mode="by_self_report",
        starting_payload={"mastered_chapter_ids": ["c1", "c2"]},
        prior_knowledge_strategy="skip",
        mastery_depth="deep",
        scope_mode="prerequisites_only",
        scope_topics=["线性代数", "概率论"],
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    assert project.goal_type == "exam"
    assert project.goal_spec["exam_name"] == "考研"
    assert project.goal_spec["target_score"] == 130
    assert project.starting_mode == "by_self_report"
    assert project.starting_payload["mastered_chapter_ids"] == ["c1", "c2"]
    assert project.prior_knowledge_strategy == "skip"
    assert project.mastery_depth == "deep"
    assert project.scope_mode == "prerequisites_only"
    assert project.scope_topics == ["线性代数", "概率论"]
    assert project.subject == "数理科学 > 数学"
