"""INC-J 重建框架 + 结构锁定 测试。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §11
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.user import User
from app.models.project import Project, ProjectTreeNode
from app.models.knowledge_point import KnowledgePoint
from app.services.project_service import project_service
from app.schemas.project import ProjectUpdate


def _fw(chapters, prefix):
    return {
        "phases": [{"name": "阶段", "weeks": 4}],
        "chapters": [
            {"title": f"{prefix}章{c}", "phase_name": "阶段", "lessons": [
                {"title": f"{prefix}课{c}_{l}", "kp_names": [f"{prefix}KP{c}_{l}"], "difficulty": "blue"}
                for l in range(2)
            ]}
            for c in range(chapters)
        ],
        "prereqs": [],
    }


_FW1 = _fw(2, "A")  # 2 章 4 课
_FW2 = _fw(3, "B")  # 3 章 6 课（不同）


async def _uid(client: AsyncClient, db, email: str):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def _count(db, proj_id):
    nodes = (await db.execute(
        select(func.count(ProjectTreeNode.id)).where(ProjectTreeNode.project_id == proj_id))).scalar()
    kps = (await db.execute(
        select(func.count(KnowledgePoint.id)).where(KnowledgePoint.project_id == proj_id))).scalar()
    names = (await db.execute(
        select(KnowledgePoint.name).where(KnowledgePoint.project_id == proj_id))).scalars().all()
    return nodes, kps, set(names)


@pytest.mark.asyncio
async def test_rebuild_clears_and_regenerates(client: AsyncClient, db, monkeypatch):
    uid = await _uid(client, db, "rebuildj@test.com")
    proj = Project(user_id=uid, name="数学", subject="数理科学 > 数学", goal_type="exam")
    db.add(proj)
    await db.commit()
    await db.refresh(proj)

    calls = {"n": 0}

    async def _gen(**k):
        calls["n"] += 1
        return _FW1 if calls["n"] == 1 else _FW2

    monkeypatch.setattr("app.services.project_service.generate_framework", _gen)

    # 首次生成 → FW1（1 根 + 2 章 + 4 课 = 7 节点，4 KP）
    await project_service.generate_tree_nodes(db, str(proj.id), str(uid))
    await db.commit()
    n1, k1, names1 = await _count(db, proj.id)
    assert n1 == 7 and k1 == 4 and any(x.startswith("A") for x in names1)

    # 重建 → 清 FW1 + 建 FW2（1 + 3 + 6 = 10 节点，6 KP），**不累积**
    await project_service.generate_tree_nodes(db, str(proj.id), str(uid), rebuild=True)
    await db.commit()
    n2, k2, names2 = await _count(db, proj.id)
    assert calls["n"] == 2, "rebuild 真重新调用 generate_framework"
    assert n2 == 10 and k2 == 6, "重建后只剩 FW2（旧树/KP 已清，未累积）"
    assert all(x.startswith("B") for x in names2), "新 KP 全来自 FW2"
    assert names1.isdisjoint(names2), "旧 FW1 KP 已删"


def test_project_update_locks_structural_params():
    # INC-J 锁：ProjectUpdate 只有 name+summary，结构参数（goal_type/mastery_depth/…）schema 层锁死
    fields = set(ProjectUpdate.model_fields.keys())
    assert fields == {"name", "summary"}
    assert "goal_type" not in fields and "mastery_depth" not in fields and "scope_mode" not in fields
