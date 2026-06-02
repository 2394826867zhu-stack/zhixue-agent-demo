"""G-P1-6 · 边自愈行为级集成：违例衰减 / 持续违例剪除 / 不动人工边 / 一致加固。"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.prerequisite_edge import PrerequisiteEdge
from app.services import edge_healing as eh


async def _user(db, email):
    u = User(email=email, password_hash="x")
    db.add(u); await db.flush()
    return u.id


async def _kp(db, uid, mastery):
    kp = KnowledgePoint(user_id=uid, name="kp", subject="math", p_mastery=mastery, mastery_status="learning")
    db.add(kp); await db.flush()
    return kp.id


async def _edge(db, uid, a, b, conf, source="llm"):
    e = PrerequisiteEdge(user_id=uid, from_kp_id=a, to_kp_id=b, confidence=conf, source=source)
    db.add(e); await db.flush()
    return e


@pytest.mark.asyncio
async def test_violated_edge_decays_confidence(db: AsyncSession):
    uid = await _user(db, "eh_decay@zhiyao.ai")
    a = await _kp(db, uid, 0.2)   # 先修没掌握
    b = await _kp(db, uid, 0.9)   # 下游明确掌握 → 违例
    e = await _edge(db, uid, a, b, 0.5)

    rep = await eh.assess_and_heal(db, str(uid))
    await db.flush(); await db.refresh(e)
    assert rep["violated"] == 1 and rep["pruned"] == 0
    assert e.confidence < 0.5          # 衰减（行为级状态变化）


@pytest.mark.asyncio
async def test_persistent_violation_prunes_edge(db: AsyncSession):
    uid = await _user(db, "eh_prune@zhiyao.ai")
    a = await _kp(db, uid, 0.1)
    b = await _kp(db, uid, 0.95)
    e = await _edge(db, uid, a, b, 0.12)   # 已接近地板，违例一次即跌破 → 剪除
    eid = e.id

    rep = await eh.assess_and_heal(db, str(uid))
    await db.flush()
    assert rep["pruned"] == 1
    gone = (await db.execute(select(PrerequisiteEdge).where(PrerequisiteEdge.id == eid))).scalar_one_or_none()
    assert gone is None                # 边被剪除 → 图谱少一行（前沿/根因随之变）


@pytest.mark.asyncio
async def test_manual_edge_never_pruned(db: AsyncSession):
    uid = await _user(db, "eh_manual@zhiyao.ai")
    a = await _kp(db, uid, 0.1)
    b = await _kp(db, uid, 0.95)
    e = await _edge(db, uid, a, b, 0.12, source="manual")
    eid = e.id

    rep = await eh.assess_and_heal(db, str(uid))
    await db.flush()
    assert rep["pruned"] == 0
    still = (await db.execute(select(PrerequisiteEdge).where(PrerequisiteEdge.id == eid))).scalar_one_or_none()
    assert still is not None            # 人工边不自动剪除


@pytest.mark.asyncio
async def test_consistent_edge_reinforced(db: AsyncSession):
    uid = await _user(db, "eh_reinforce@zhiyao.ai")
    a = await _kp(db, uid, 0.7)
    b = await _kp(db, uid, 0.7)
    e = await _edge(db, uid, a, b, 0.5)

    rep = await eh.assess_and_heal(db, str(uid))
    await db.flush(); await db.refresh(e)
    assert rep["consistent"] == 1
    assert e.confidence > 0.5           # 加固


@pytest.mark.asyncio
async def test_empty_safe(db: AsyncSession):
    uid = await _user(db, "eh_empty@zhiyao.ai")
    rep = await eh.assess_and_heal(db, str(uid))
    assert rep == {"n_edges": 0, "violated": 0, "consistent": 0, "pruned": 0, "details": []}
