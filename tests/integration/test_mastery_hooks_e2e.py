"""学习内核 P0 · 答题钩子端到端集成测试（审计 A-1）。

价值：验证三个真实答题入口（training.submit_answer / feynman.submit / fsrs.review）
确实会触发掌握度更新——这是 P0-4 的核心集成，此前零覆盖（钩子被删/错位也不会被测试发现）。

为保持确定性：monkeypatch 掉 LLM 评分层与 fsrs 的 fire-and-forget 副作用，
只断言"经真实入口调用后 kp.p_mastery / last_probe 被正确改写"。
"""
import uuid

import pytest

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession, TrainingQuestion
from app.services import measurement_service
from app.services.training_service import training_service
from app.services.fsrs_service import fsrs_service
from app.services.feynman_service import feynman_service
from app.schemas.training import AnswerRequest

pytestmark = pytest.mark.asyncio


async def _make_user(db) -> User:
    user = User(
        email=f"hook_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="钩子测试",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_kp(db, user, *, p_mastery=None) -> KnowledgePoint:
    kp = KnowledgePoint(
        user_id=user.id, name="牛顿第二定律", content="F=ma",
        bloom_level="apply", subject="物理", p_mastery=p_mastery,
    )
    db.add(kp)
    await db.flush()
    return kp


# ---------- 钩子①：training.submit_answer ----------

async def test_training_submit_answer_correct_raises_mastery(db, monkeypatch):
    user = await _make_user(db)
    kp = await _make_kp(db, user, p_mastery=0.3)
    session = TrainingSession(user_id=user.id, mode="single_kp", subject="物理",
                              knowledge_point_id=kp.id, question_count=1)
    db.add(session)
    await db.flush()
    q = TrainingQuestion(
        session_id=session.id, user_id=user.id, knowledge_point_id=kp.id,
        bloom_level="apply", question_type="fill_blank",
        question_text="F=?", reference_answer="ma",
    )
    db.add(q)
    await db.flush()

    # 评分层 → 固定"答对"。_grade_answer 返回 (score, feedback, is_wrong, error_reason)
    async def _fake_grade(self, question, user_answer):
        return 90, "对了", False, None
    monkeypatch.setattr(training_service.__class__, "_grade_answer", _fake_grade)

    await training_service.submit_answer(
        db, session_id=str(session.id), question_id=str(q.id),
        user_id=str(user.id), data=AnswerRequest(user_answer="ma"),
    )
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.p_mastery > 0.3


async def test_training_submit_probe_writes_last_probe_not_mistake(db, monkeypatch):
    user = await _make_user(db)
    kp = await _make_kp(db, user, p_mastery=0.6)
    session = TrainingSession(user_id=user.id, mode="single_kp", subject="物理",
                              knowledge_point_id=kp.id, question_count=1)
    db.add(session)
    await db.flush()
    # 探针题答错：应写 last_probe，且不归档为错题
    q = TrainingQuestion(
        session_id=session.id, user_id=user.id, knowledge_point_id=kp.id,
        bloom_level="apply", question_type="fill_blank",
        question_text="F=?", reference_answer="ma",
        is_probe=True, probe_kind="retention",
    )
    db.add(q)
    await db.flush()

    # _grade_answer 返回 (score, feedback, is_wrong, error_reason)：答错
    async def _fake_grade(self, question, user_answer):
        return 10, "错了", True, "concept"
    monkeypatch.setattr(training_service.__class__, "_grade_answer", _fake_grade)

    # 若探针误走错题归档，会调用 rag_index.enqueue_mistake_index → 这里探测它是否被调用
    called = {"mistake": False}
    from app.services import rag_index
    monkeypatch.setattr(rag_index, "enqueue_mistake_index",
                        lambda *a, **k: called.__setitem__("mistake", True))

    await training_service.submit_answer(
        db, session_id=str(session.id), question_id=str(q.id),
        user_id=str(user.id), data=AnswerRequest(user_answer="错"),
    )
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.last_probe is not None
    assert refreshed.last_probe["kind"] == "retention"
    assert called["mistake"] is False  # 探针不归档错题


# ---------- 钩子②：feynman.submit ----------

async def test_feynman_submit_high_score_raises_mastery(db, monkeypatch):
    user = await _make_user(db)
    kp = await _make_kp(db, user, p_mastery=0.3)

    # grade LLM → 高分（total = 90*0.4+90*0.3+90*0.3 = 90 ≥ 70）
    async def _fake_generate(*args, **kwargs):
        return '{"accuracy_score": 90, "completeness_score": 90, "clarity_score": 90, "gaps": [], "ai_feedback": "清楚"}'
    import app.services.feynman_service as fsvc
    monkeypatch.setattr(fsvc.llm_client, "generate", _fake_generate)

    await feynman_service.submit(
        db, user_id=str(user.id), kp_id=str(kp.id),
        user_explanation="牛顿第二定律说合外力等于质量乘加速度",
    )
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.p_mastery > 0.3


# ---------- 钩子③：fsrs.review ----------

async def test_fsrs_review_good_rating_raises_mastery(db, monkeypatch):
    user = await _make_user(db)
    kp = await _make_kp(db, user, p_mastery=0.3)
    card = await fsrs_service.create_card(
        db, user_id=str(user.id), knowledge_point_id=str(kp.id),
        front="F=?", back="ma", card_type="concept",
    )

    # 屏蔽 fire-and-forget 副作用（_post_review_side_effects 是模块级函数，独立 session 发奖励，测试中易 flaky）
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr("app.services.fsrs_service._post_review_side_effects", _noop)

    await fsrs_service.review(db, card_id=str(card.id), user_id=str(user.id), rating=4)
    refreshed = await db.get(KnowledgePoint, kp.id)
    assert refreshed.p_mastery > 0.3
