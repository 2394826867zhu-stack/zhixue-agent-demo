"""INC-C _build_tree_from_framework：难度取自 LLM 每课 + 先修边取自 prereqs[]（非线性）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §7.4
证明两点（相对旧版）：
- 难度不再 `_DIFF[phase.sort_order]` 硬分配 → 同 phase 内多种难度并存。
- 先修边来自真 prereqs[]（跨章/非相邻），不是相邻课时线性链。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.models.project import Project, ProjectTreeNode
from app.models.knowledge_point import KnowledgePoint
from app.models.prerequisite_edge import PrerequisiteEdge
from app.services.project_service import project_service


async def _uid(client: AsyncClient, db, email: str):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


def _framework() -> dict:
    return {
        "phases": [
            {"name": "阶段一", "description": "入门", "weeks": 4},
            {"name": "阶段二", "description": "进阶", "weeks": 4},
        ],
        "chapters": [
            {"title": "极限与连续", "phase_name": "阶段一", "lessons": [
                {"title": "数列极限", "kp_names": ["数列极限"], "difficulty": "blue"},
                {"title": "函数极限", "kp_names": ["函数极限"], "difficulty": "blue"},
                {"title": "连续性", "kp_names": ["连续性"], "difficulty": "purple"},
                {"title": "间断点", "kp_names": ["间断点"], "difficulty": "purple", "optional": True},
            ]},
            {"title": "导数与微分", "phase_name": "阶段二", "lessons": [
                {"title": "导数定义", "kp_names": ["导数定义"], "difficulty": "purple"},
                {"title": "求导法则", "kp_names": ["求导法则"], "difficulty": "blue"},
                {"title": "中值定理", "kp_names": ["中值定理"], "difficulty": "gold"},
                {"title": "泰勒展开", "kp_names": ["泰勒展开"], "difficulty": "gold"},
            ]},
        ],
        # 真依赖：跨章 + 非相邻（连续性→导数定义），不是相邻顺序链
        "prereqs": [
            ["函数极限", "连续性"],
            ["连续性", "导数定义"],
            ["导数定义", "求导法则"],
            ["导数定义", "中值定理"],
            ["中值定理", "泰勒展开"],
        ],
    }


@pytest.mark.asyncio
async def test_build_difficulty_from_llm(client: AsyncClient, db):
    uid = await _uid(client, db, "incc_diff@test.com")
    proj = Project(user_id=uid, name="高数", subject="数理科学 > 数学",
                   goal_type="exam", mastery_depth="deep")
    db.add(proj)
    await db.commit()
    await db.refresh(proj)

    await project_service._build_tree_from_framework(db, proj, _framework())
    await db.commit()

    lessons = (await db.execute(
        select(ProjectTreeNode)
        .where(ProjectTreeNode.project_id == proj.id, ProjectTreeNode.depth == 2)
        .order_by(ProjectTreeNode.sort_order)
    )).scalars().all()
    by_title = {n.title: n for n in lessons}

    # 难度取自 LLM 每课返回值（非 phase 序号硬分配）
    assert by_title["中值定理"].difficulty == "gold"
    assert by_title["泰勒展开"].difficulty == "gold"
    assert by_title["数列极限"].difficulty == "blue"
    assert by_title["连续性"].difficulty == "purple"
    # 同一框架内 ≥3 种难度并存 → 证明非"同 phase 全同色"硬分配
    assert len({n.difficulty for n in lessons}) >= 3
    # optional 课时移出主干高亮
    assert by_title["间断点"].is_on_main_path is False
    assert by_title["数列极限"].is_on_main_path is True


@pytest.mark.asyncio
async def test_build_prereq_edges_from_names(client: AsyncClient, db):
    uid = await _uid(client, db, "incc_prereq@test.com")
    proj = Project(user_id=uid, name="高数", subject="数理科学 > 数学", goal_type="exam")
    db.add(proj)
    await db.commit()
    await db.refresh(proj)

    await project_service._build_tree_from_framework(db, proj, _framework())
    await db.commit()

    kps = (await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.project_id == proj.id)
    )).scalars().all()
    nid = {k.name: k.id for k in kps}
    edges = (await db.execute(
        select(PrerequisiteEdge).where(PrerequisiteEdge.user_id == uid)
    )).scalars().all()
    edge_set = {(e.from_kp_id, e.to_kp_id) for e in edges}

    # 真依赖（跨章 / 非相邻）落地
    assert (nid["连续性"], nid["导数定义"]) in edge_set
    assert (nid["导数定义"], nid["中值定理"]) in edge_set
    # 相邻顺序对（间断点 sort4 → 导数定义 sort5）不在真依赖里 → 不应被当成边
    assert (nid["间断点"], nid["导数定义"]) not in edge_set
