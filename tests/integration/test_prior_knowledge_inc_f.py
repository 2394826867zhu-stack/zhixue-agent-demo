"""INC-F 先验知识 → L2 播种：勾掌握章节按 strategy 播种节点状态 + KP p_mastery（喂 L2）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §9
治理铁律：只播种 L2 的输入态（KP p_mastery/mastery_status + 节点 status），不另立解锁权威；
mastery_depth 阈值作 L2 完成判断输入参数（seeding 据项目深度定 seed mastery）。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.models.project import Project, ProjectTreeNode
from app.models.knowledge_point import KnowledgePoint
from app.services.project_service import project_service
from app.services.learner_state_service import mastery_threshold

_FRAMEWORK = {
    "phases": [{"name": "阶段一", "weeks": 4}, {"name": "阶段二", "weeks": 4}],
    "chapters": [
        {"title": "极限与连续", "phase_name": "阶段一", "lessons": [
            {"title": "数列极限", "kp_names": ["数列极限"], "difficulty": "blue"},
            {"title": "函数极限", "kp_names": ["函数极限"], "difficulty": "blue"},
            {"title": "连续性", "kp_names": ["连续性"], "difficulty": "purple"},
            {"title": "间断点", "kp_names": ["间断点"], "difficulty": "purple"},
        ]},
        {"title": "导数与微分", "phase_name": "阶段二", "lessons": [
            {"title": "导数定义", "kp_names": ["导数定义"], "difficulty": "purple"},
            {"title": "求导法则", "kp_names": ["求导法则"], "difficulty": "blue"},
            {"title": "中值定理", "kp_names": ["中值定理"], "difficulty": "gold"},
            {"title": "泰勒展开", "kp_names": ["泰勒展开"], "difficulty": "gold"},
        ]},
    ],
    "prereqs": [["连续性", "导数定义"]],
}


async def _uid(client: AsyncClient, db, email: str):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def _build(db, uid, **proj_kw):
    proj = Project(user_id=uid, name="高数", subject="数理科学 > 数学", **proj_kw)
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    await project_service._build_tree_from_framework(db, proj, _FRAMEWORK)
    await db.commit()
    return proj


async def _nodes_kps(db, proj):
    lessons = {n.title: n for n in (await db.execute(
        select(ProjectTreeNode).where(
            ProjectTreeNode.project_id == proj.id, ProjectTreeNode.depth == 2))).scalars().all()}
    kps = {k.name: k for k in (await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.project_id == proj.id))).scalars().all()}
    return lessons, kps


@pytest.mark.asyncio
async def test_self_report_skip_seeds_l2(client: AsyncClient, db):
    uid = await _uid(client, db, "pkskip@test.com")
    proj = await _build(
        db, uid, starting_mode="by_self_report", prior_knowledge_strategy="skip",
        starting_payload={"mastered_chapter_ids": ["极限与连续"]}, mastery_depth="deep")
    lessons, kps = await _nodes_kps(db, proj)

    # 掌握章节课时 → completed + KP mastered + p_mastery 清掌握线(deep=0.9)
    assert lessons["数列极限"].status == "completed" and lessons["数列极限"].completion_pct == 1.0
    assert kps["数列极限"].mastery_status == "mastered" and kps["数列极限"].p_mastery >= 0.9
    assert kps["连续性"].p_mastery >= 0.9
    # 未勾章节 → KP 仍 new/unprobed（L2 不会当已掌握）
    assert kps["导数定义"].mastery_status == "new" and kps["导数定义"].p_mastery is None
    # 首个未掌握课时可学（导数章第一节）
    assert lessons["导数定义"].status == "available"


@pytest.mark.asyncio
async def test_self_report_review_seeds_available(client: AsyncClient, db):
    uid = await _uid(client, db, "pkreview@test.com")
    proj = await _build(
        db, uid, starting_mode="by_self_report", prior_knowledge_strategy="review",
        starting_payload={"mastered_chapter_ids": ["极限与连续"]}, mastery_depth="working")
    lessons, kps = await _nodes_kps(db, proj)
    # review → available(可快速复习不强制) + KP reviewing + p_mastery 略低于掌握线(working 0.7→0.6)
    assert lessons["连续性"].status == "available"
    assert kps["连续性"].mastery_status == "reviewing"
    assert 0.5 <= kps["连续性"].p_mastery < 0.7


def test_mastery_threshold_mapping():
    # mastery_depth → 完成阈值（spec §5.2），L2 完成判断的输入参数
    assert mastery_threshold("surface") == 0.5
    assert mastery_threshold("working") == 0.7
    assert mastery_threshold("deep") == 0.9
    assert mastery_threshold(None) == 0.7  # 兜底 working


@pytest.mark.asyncio
async def test_from_scratch_no_seeding(client: AsyncClient, db):
    uid = await _uid(client, db, "pkscratch@test.com")
    proj = await _build(db, uid, starting_mode="from_scratch")
    _, kps = await _nodes_kps(db, proj)
    assert all(k.mastery_status == "new" and k.p_mastery is None for k in kps.values())
    first = (await db.execute(
        select(ProjectTreeNode).where(
            ProjectTreeNode.project_id == proj.id, ProjectTreeNode.depth == 2)
        .order_by(ProjectTreeNode.sort_order).limit(1))).scalar_one()
    assert first.status == "available"
