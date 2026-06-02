"""G-P4-1 · 探针回流闭环 — 行为级集成（闭环可见）。

验证探针失败真的改变调度/状态：闪卡提前到期、掌握度下调、mastery_status 退回。
"""
import uuid
import pytest
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.services import probe_feedback


async def _user(db: AsyncSession, email: str) -> uuid.UUID:
    u = User(email=email, password_hash="x")
    db.add(u)
    await db.flush()
    return u.id


async def _kp_with_card(db, uid, *, p_mastery, status, stability, due_in_days):
    kp = KnowledgePoint(user_id=uid, name="kp", subject="math", p_mastery=p_mastery, mastery_status=status)
    db.add(kp)
    await db.flush()
    card = Flashcard(
        knowledge_point_id=kp.id, user_id=uid, card_type="basic", front="q", back="a",
        stability=stability, due_date=date.today() + timedelta(days=due_in_days),
    )
    db.add(card)
    await db.flush()
    return kp, card


@pytest.mark.asyncio
async def test_transfer_fail_demotes_and_pulls_card_due(db: AsyncSession):
    uid = await _user(db, "pf_transfer@zhiyao.ai")
    kp, card = await _kp_with_card(db, uid, p_mastery=0.85, status="mastered", stability=20.0, due_in_days=15)

    decision = await probe_feedback.apply_probe_feedback(db, kp.id, "transfer", correct=False)
    await db.flush()
    await db.refresh(kp); await db.refresh(card)

    assert decision["demote"] is True and decision["reschedule"] == "sooner"
    # 掌握度被 BKT 下调
    assert kp.p_mastery < 0.85
    # 退回 learning（重回前沿）
    assert kp.mastery_status == "learning"
    # 闪卡提前到期 + stability 缩小（闭环可见）
    assert card.due_date == date.today()
    assert card.stability < 20.0
    assert kp.last_probe["schedule_action"] == "sooner"
    assert kp.last_probe["demoted"] is True


@pytest.mark.asyncio
async def test_retention_fail_reschedules_not_demote(db: AsyncSession):
    uid = await _user(db, "pf_retention@zhiyao.ai")
    kp, card = await _kp_with_card(db, uid, p_mastery=0.7, status="mastered", stability=10.0, due_in_days=7)

    decision = await probe_feedback.apply_probe_feedback(db, kp.id, "retention", correct=False)
    await db.flush()
    await db.refresh(kp); await db.refresh(card)

    assert decision["reschedule"] == "sooner" and decision["demote"] is False
    assert card.due_date == date.today()        # 提前复习
    assert card.stability < 10.0
    assert kp.mastery_status == "mastered"       # 留存失败不降级状态（只是忘了，没说不懂）


@pytest.mark.asyncio
async def test_probe_pass_no_reschedule(db: AsyncSession):
    uid = await _user(db, "pf_pass@zhiyao.ai")
    kp, card = await _kp_with_card(db, uid, p_mastery=0.6, status="learning", stability=8.0, due_in_days=5)
    orig_due = card.due_date

    await probe_feedback.apply_probe_feedback(db, kp.id, "retention", correct=True)
    await db.flush()
    await db.refresh(card)

    assert card.due_date == orig_due             # 通过不强行改期
    assert card.stability == 8.0


@pytest.mark.asyncio
async def test_none_kp_safe(db: AsyncSession):
    decision = await probe_feedback.apply_probe_feedback(db, None, "retention", correct=False)
    assert decision["reschedule"] == "sooner"  # 决策仍返回，但无 KP 可改
