"""P0-2（2026-06-29 审计）confirm 路径框架硬化回归测试。

确认 confirm 不再盲信客户端回传的 framework_json：
- 扁平/非法框架（绕过 F1 validate_framework 的规模/反扁平闸）→ 不建脏树，退 phases 兜底。
- 超长 subject（>50）→ KP.subject 截断不致建树事务 500。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.models.user import User
from app.models.project import ProjectTreeNode
from app.models.knowledge_point import KnowledgePoint
from app.schemas.project import ProjectInitDraft, ProjectConfirmRequest
from app.services.project_service import project_service

# 合法框架（≥8 课时，过 validate_framework）
_VALID_FRAMEWORK = {
    "phases": [{"name": "阶段一", "weeks": 4}, {"name": "阶段二", "weeks": 4}],
    "chapters": [
        {"title": "基础", "phase_name": "阶段一", "lessons": [
            {"title": f"课{i}", "kp_names": [f"课{i}"], "difficulty": "blue"} for i in range(5)
        ]},
        {"title": "进阶", "phase_name": "阶段二", "lessons": [
            {"title": f"课{i}", "kp_names": [f"课{i}"], "difficulty": "purple"} for i in range(5, 9)
        ]},
    ],
    "prereqs": [],
}

# 扁平占位框架（1 章 1 课，total_lessons < max(chapters, 8) → validate 不过）
_FLAT_FRAMEWORK = {
    "phases": [{"name": "唯一阶段", "weeks": 2}],
    "chapters": [{"title": "占位章", "phase_name": "唯一阶段",
                  "lessons": [{"title": "占位课", "kp_names": ["x"]}]}],
    "prereqs": [],
}


async def _uid(client: AsyncClient, db, email: str):
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


@pytest.mark.asyncio
async def test_confirm_rejects_flat_framework_no_dirty_tree(client: AsyncClient, db, monkeypatch):
    uid = await _uid(client, db, "p02flat@test.com")

    async def _fake_gen(**k):
        return _VALID_FRAMEWORK

    monkeypatch.setattr("app.services.project_service.generate_framework", _fake_gen)
    card = await project_service.create_from_draft(
        db, str(uid), ProjectInitDraft(name="X", summary="", subject="数学"))

    # 模拟客户端把缓存框架篡改成扁平占位（绕过 F1 规模闸的攻击面）
    card.framework_json = _FLAT_FRAMEWORK
    proj = await project_service.confirm_preview(db, str(uid), ProjectConfirmRequest(preview=card))

    # 校验不过 → 退 phases 兜底，不建脏树
    n = (await db.execute(
        select(func.count(ProjectTreeNode.id)).where(ProjectTreeNode.project_id == proj.id)
    )).scalar()
    assert n == 0, "扁平框架不应建树"
    assert len(proj.phases) >= 1, "退 phases 兜底"


@pytest.mark.asyncio
async def test_confirm_oversized_subject_truncates_not_500(client: AsyncClient, db, monkeypatch):
    uid = await _uid(client, db, "p02subj@test.com")
    long_subject = "数" * 70  # >50，KP.subject 仅 String(50)

    async def _fake_gen(**k):
        return _VALID_FRAMEWORK

    monkeypatch.setattr("app.services.project_service.generate_framework", _fake_gen)
    card = await project_service.create_from_draft(
        db, str(uid), ProjectInitDraft(name="X", summary="", subject=long_subject))

    # 不应抛 DataError/500
    proj = await project_service.confirm_preview(db, str(uid), ProjectConfirmRequest(preview=card))
    assert proj.framework_status == "ready"

    kp_subjects = (await db.execute(
        select(KnowledgePoint.subject).where(KnowledgePoint.project_id == proj.id)
    )).scalars().all()
    assert kp_subjects, "应建出 KP"
    assert all(s is None or len(s) <= 50 for s in kp_subjects), "KP.subject 必须截断到 50"
