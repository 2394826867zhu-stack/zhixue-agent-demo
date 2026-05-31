"""学习内核 P1 · 先修图谱建边 + 防环 集成测试。"""
import uuid

import pytest

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.prerequisite_edge import PrerequisiteEdge
from app.services import graph_service
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def _make_user(db) -> User:
    user = User(email=f"graph_{uuid.uuid4().hex[:8]}@test.local",
                password_hash="x", nickname="图谱测试")
    db.add(user)
    await db.flush()
    return user


async def _kp(db, user, name) -> KnowledgePoint:
    kp = KnowledgePoint(user_id=user.id, name=name, content="...",
                        bloom_level="apply", subject="物理")
    db.add(kp)
    await db.flush()
    return kp


async def test_add_edges_persists_and_blocks_cycle(db):
    user = await _make_user(db)
    a = await _kp(db, user, "向量")
    b = await _kp(db, user, "力的合成")
    # A->B 正常落库；再加 B->A 应被环检测拦截
    n1 = await graph_service.add_edges(db, user.id, [
        {"from_kp_id": a.id, "to_kp_id": b.id, "confidence": 0.9, "source": "llm"},
    ])
    n2 = await graph_service.add_edges(db, user.id, [
        {"from_kp_id": b.id, "to_kp_id": a.id, "confidence": 0.9, "source": "llm"},
    ])
    await db.flush()
    assert n1 == 1
    assert n2 == 0  # 成环被拒
    rows = await db.execute(select(PrerequisiteEdge).where(PrerequisiteEdge.user_id == user.id))
    edges = rows.scalars().all()
    assert len(edges) == 1
    assert str(edges[0].from_kp_id) == str(a.id)


async def test_add_edges_dedups(db):
    user = await _make_user(db)
    a = await _kp(db, user, "导数")
    b = await _kp(db, user, "求导法则")
    payload = [{"from_kp_id": a.id, "to_kp_id": b.id, "confidence": 0.8, "source": "llm"}]
    assert await graph_service.add_edges(db, user.id, payload) == 1
    await db.flush()
    # 重复同一条边 → 0
    assert await graph_service.add_edges(db, user.id, payload) == 0


async def test_build_edges_for_kps_uses_llm(db, monkeypatch):
    user = await _make_user(db)
    a = await _kp(db, user, "一元一次方程")
    b = await _kp(db, user, "一元二次方程")

    async def _fake_generate(*args, **kwargs):
        return '{"edges": [{"from": 0, "to": 1, "confidence": 0.9, "reason": "先会一次再会二次"}]}'
    monkeypatch.setattr("app.llm.client.llm_client.generate", _fake_generate)

    n = await graph_service.build_edges_for_kps(db, user.id, [a, b])
    await db.flush()
    assert n == 1
    rows = await db.execute(select(PrerequisiteEdge).where(PrerequisiteEdge.user_id == user.id))
    edges = rows.scalars().all()
    assert len(edges) == 1
    assert str(edges[0].from_kp_id) == str(a.id)
    assert str(edges[0].to_kp_id) == str(b.id)


async def test_build_edges_for_kps_llm_failure_is_safe(db, monkeypatch):
    user = await _make_user(db)
    a = await _kp(db, user, "X")
    b = await _kp(db, user, "Y")

    async def _boom(*args, **kwargs):
        raise RuntimeError("LLM down")
    monkeypatch.setattr("app.llm.client.llm_client.generate", _boom)

    # 不抛异常，返回 0（不阻断建 KP）
    assert await graph_service.build_edges_for_kps(db, user.id, [a, b]) == 0


# ---------- T4 诊断增强：可学习前沿 + 根因 ----------

async def _kp_m(db, user, name, p_mastery) -> KnowledgePoint:
    kp = KnowledgePoint(user_id=user.id, name=name, content="...",
                        bloom_level="apply", subject="物理", p_mastery=p_mastery)
    db.add(kp)
    await db.flush()
    return kp


async def test_diagnose_returns_learning_frontier(db):
    from app.services.agent_tools import _diagnose_learning
    user = await _make_user(db)
    a = await _kp_m(db, user, "矢量基础", 0.9)   # 已掌握
    b = await _kp_m(db, user, "力的合成", 0.2)   # 未掌握，先修 a 已掌握 → 前沿
    c = await _kp_m(db, user, "动力学", 0.2)     # 未掌握，先修 b 未掌握 → 不在前沿
    await graph_service.add_edges(db, user.id, [
        {"from_kp_id": a.id, "to_kp_id": b.id, "confidence": 0.9, "source": "llm"},
        {"from_kp_id": b.id, "to_kp_id": c.id, "confidence": 0.9, "source": "llm"},
    ])
    await db.flush()

    result = await _diagnose_learning(db, user.id)
    frontier_names = {f["name"] for f in result.get("learning_frontier", [])}
    assert "力的合成" in frontier_names
    assert "动力学" not in frontier_names
    assert "矢量基础" not in frontier_names  # 已掌握不在前沿


async def test_diagnose_annotates_root_cause(db, monkeypatch):
    from app.services import training_service as tsvc
    from app.services.agent_tools import _diagnose_learning
    from app.models.training import TrainingSession, TrainingQuestion

    user = await _make_user(db)
    a = await _kp_m(db, user, "整式运算", 0.2)   # 塌陷的地基
    b = await _kp_m(db, user, "因式分解", 0.9)
    c = await _kp_m(db, user, "解二次方程", 0.3)  # 反复错的点
    # 边：a->c, a 未掌握 → c 的根因是 a
    await graph_service.add_edges(db, user.id, [
        {"from_kp_id": a.id, "to_kp_id": c.id, "confidence": 0.9, "source": "llm"},
    ])
    # 造一道 c 的错题
    sess = TrainingSession(user_id=user.id, mode="single_kp", subject="数学",
                           knowledge_point_id=c.id, question_count=1)
    db.add(sess)
    await db.flush()
    q = TrainingQuestion(session_id=sess.id, user_id=user.id, knowledge_point_id=c.id,
                         bloom_level="apply", question_type="calculation",
                         question_text="解 x^2-5x+6=0", reference_answer="x=2或3",
                         is_wrong=True, error_reason="concept", answered_at=None)
    db.add(q)
    await db.flush()

    result = await _diagnose_learning(db, user.id)
    # recent_mistakes 中该错题应带 root_cause 指向"整式运算"
    rc = [m.get("root_cause") for m in result.get("recent_mistakes", [])]
    assert "整式运算" in rc
