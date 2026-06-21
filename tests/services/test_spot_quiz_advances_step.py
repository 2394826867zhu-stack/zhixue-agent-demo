"""Task A4 · spot_quiz 成功出题后推进 lesson_plan.current_index（PathStepper 步进）。

生成式教学规则：每讲完一个核心概念 → 调 spot_quiz 出随堂题。本测试锁住：
spot_quiz_service.generate_for_kp 真出了题（LLM stub 返回 1 道）且挂在某个
StudySpace session 上时，把该 session 的 lesson_plan.current_index 前进一步（讲完一
个概念→推进），且封顶不越界（多次调用不超过 len(steps)）。

LLM 出题经 monkeypatch 桩掉 `spot_quiz_service.llm_client.generate` 返回 1 道题。
"""
import json
import uuid

import pytest

from app.models.user import User
from app.models.curriculum import CurriculumChapter
from app.models.knowledge_point import KnowledgePoint
from app.models.studyspace import StudySpaceSession
from app.services.spot_quiz_service import spot_quiz_service

pytestmark = pytest.mark.asyncio


async def _seed(db) -> tuple[User, KnowledgePoint, StudySpaceSession]:
    user = User(
        email=f"spot_step_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="步进测试",
    )
    db.add(user)
    await db.flush()

    chapter = CurriculumChapter(
        subject="math",
        grade_type="senior",
        grade_year=1,
        semester=1,
        chapter_index=1,
        chapter_title="导数",
        lesson_index=1,
        lesson_title="导数的定义",
    )
    db.add(chapter)
    await db.flush()

    kp = KnowledgePoint(
        user_id=user.id,
        name="导数的定义",
        content="导数是函数的瞬时变化率",
        bloom_level="understand",
        subject="math",
    )
    db.add(kp)
    await db.flush()

    ss = StudySpaceSession(
        user_id=user.id,
        chapter_id=chapter.id,
        session_type="lesson",
        status="active",
        lesson_plan={"steps": ["A", "B", "C"], "current_index": 0},
    )
    db.add(ss)
    await db.flush()
    return user, kp, ss


def _stub_one_question(monkeypatch):
    async def _fake_generate(*args, **kwargs):
        return json.dumps([
            {
                "question_type": "fill_blank",
                "question_text": "导数的几何意义是____。",
                "reference_answer": "切线斜率",
            }
        ])
    monkeypatch.setattr(
        "app.services.spot_quiz_service.llm_client.generate", _fake_generate
    )


async def test_spot_quiz_advances_current_index(db, monkeypatch):
    """成功出题 + 挂在 ss → current_index 从 0 前进到 1。"""
    user, kp, ss = await _seed(db)
    await db.commit()
    _stub_one_question(monkeypatch)

    result = await spot_quiz_service.generate_for_kp(
        db,
        user_id=str(user.id),
        kp_id=str(kp.id),
        ss_session_id=str(ss.id),
        count=1,
    )
    assert len(result["questions"]) == 1  # 确实出了题

    await db.refresh(ss)
    assert ss.lesson_plan["current_index"] == 1


async def test_spot_quiz_current_index_capped_at_steps_len(db, monkeypatch):
    """多次调用不越界：current_index 封顶于 len(steps)。"""
    user, kp, ss = await _seed(db)
    # 预置已到倒数第二步（steps=3，index 已=2）
    ss.lesson_plan = {"steps": ["A", "B", "C"], "current_index": 2}
    await db.commit()
    _stub_one_question(monkeypatch)

    # 第一次：2 -> 3（= len，封顶）
    await spot_quiz_service.generate_for_kp(
        db, user_id=str(user.id), kp_id=str(kp.id),
        ss_session_id=str(ss.id), count=1,
    )
    await db.refresh(ss)
    assert ss.lesson_plan["current_index"] == 3

    # 第二次：仍封顶在 3，不越界
    await spot_quiz_service.generate_for_kp(
        db, user_id=str(user.id), kp_id=str(kp.id),
        ss_session_id=str(ss.id), count=1,
    )
    await db.refresh(ss)
    assert ss.lesson_plan["current_index"] == 3
