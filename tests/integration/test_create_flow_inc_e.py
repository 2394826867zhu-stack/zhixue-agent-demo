"""INC-E preview→confirm 两段流：生成挪进 preview，confirm 从缓存建树（不重 LLM）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §8
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.user import User
from app.models.project import Project, ProjectTreeNode
from app.schemas.project import ProjectInitDraft, ProjectCreate, ProjectConfirmRequest
from app.services.project_service import project_service

_FRAMEWORK = {
    "phases": [{"name": "阶段一", "description": "入门", "weeks": 4},
               {"name": "阶段二", "description": "进阶", "weeks": 4}],
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
    "prereqs": [["连续性", "导数定义"], ["导数定义", "中值定理"]],
}


async def _uid(client: AsyncClient, db, email: str):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


@pytest.mark.asyncio
async def test_preview_confirm_flow_generates_once(client: AsyncClient, db, monkeypatch):
    uid = await _uid(client, db, "flowE@test.com")
    calls = {"n": 0}

    async def _fake_gen(**k):
        calls["n"] += 1
        return _FRAMEWORK

    monkeypatch.setattr("app.services.project_service.generate_framework", _fake_gen)

    draft = ProjectInitDraft(
        name="考研数学", summary="", subject="数理科学 > 数学",
        goal_type="exam", mastery_depth="deep", weekly_hours=10,
    )

    # 1. preview：生成真框架 + 可行性 → 卡（缓存框架）
    card = await project_service.create_from_draft(db, str(uid), draft)
    assert calls["n"] == 1, "preview 调用一次 generate_framework"
    assert len(card.framework_preview) == 2  # 2 章
    assert card.framework_preview[0].chapter_title == "极限与连续"
    assert card.proposed_tree_summary["total_nodes"] == 8
    assert card.proposed_tree_summary["gold_count"] == 2
    assert card.feasibility["band"] in ("ample", "fit", "tight", "infeasible")
    assert card.framework_json.get("chapters"), "框架缓存进卡"

    # 2. confirm：从缓存建树，不重新调 LLM
    proj = await project_service.confirm_preview(db, str(uid), ProjectConfirmRequest(preview=card))
    assert calls["n"] == 1, "confirm 用缓存，不再调 generate_framework"
    assert proj.framework_status == "ready"
    assert proj.goal_type == "exam" and proj.mastery_depth == "deep"  # v3 字段持久化
    # 树就位：1 根 + 2 章 + 8 课 = 11
    node_count = (await db.execute(
        select(func.count(ProjectTreeNode.id)).where(ProjectTreeNode.project_id == proj.id)
    )).scalar()
    assert node_count == 11


@pytest.mark.asyncio
async def test_confirm_without_framework_builds_phases_defers_tree(client: AsyncClient, db, monkeypatch):
    """无缓存框架（NL/onboarding 路径）确认 → 建调性 phases + 空树（树延后 /tree/generate）。

    不强制 framework_status=failed（onboarding D10 不在本轮改，保持旧行为）。
    """
    uid = await _uid(client, db, "flowEnofw@test.com")
    monkeypatch.setattr("app.services.project_service.generate_framework",
                        lambda **k: _async_none())
    card = await project_service.create_from_draft(
        db, str(uid), ProjectInitDraft(name="X", summary="", subject="数学"))
    assert card.framework_preview == [] and not card.framework_json
    proj = await project_service.confirm_preview(db, str(uid), ProjectConfirmRequest(preview=card))
    assert len(proj.phases) >= 1  # 退调性 phases 兜底展示
    # 无框架 → 不建树（树留 /tree/generate）
    n = (await db.execute(
        select(func.count(ProjectTreeNode.id)).where(ProjectTreeNode.project_id == proj.id)
    )).scalar()
    assert n == 0


async def _async_none():
    return None


@pytest.mark.asyncio
async def test_create_direct_fast_path_persists_v3(client: AsyncClient, db):
    """POST /projects 极简快路径：持久化 v3 字段 + 建调性 phases（树由 /tree/generate 单独建）。"""
    uid = await _uid(client, db, "fastE@test.com")
    proj = await project_service.create_project(
        db, str(uid), ProjectCreate(name="极简项目", goal_type="skill", mastery_depth="working"))
    assert proj.goal_type == "skill" and proj.mastery_depth == "working"
    assert proj.scope_mode == "full_subject"  # 默认
    assert len(proj.phases) >= 1
