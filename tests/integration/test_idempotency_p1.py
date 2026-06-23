"""P1-3 / P1-4 · 并发幂等：训练重复提交 + StudySpace 重复完成发星。

单会话测试不能真并发，此处用顺序"二次调用"锁定原子抢占/状态机的可观测行为
（第二次被拒 + 计数/发星不翻倍）；真并发由 atomic UPDATE…WHERE 的行锁保证。
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func

from app.core.exceptions import ValidationError, AppError
from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession, TrainingQuestion
from app.models.studyspace import StudySpaceSession
from app.models.curriculum import CurriculumChapter
from app.models.star import StarLedger
from app.schemas.training import AnswerRequest
from app.services.training_service import training_service
from app.services.studyspace_service import StudySpaceService

studyspace_service = StudySpaceService()


async def _uid(client: AsyncClient, db, email: str) -> str:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return str((await db.execute(select(User.id).where(User.email == email))).scalar_one())


@pytest.mark.asyncio
async def test_submit_answer_double_is_rejected(client: AsyncClient, db, monkeypatch):
    uid = await _uid(client, db, "submit_dup@zhiyao.ai")
    kp = KnowledgePoint(user_id=uuid.UUID(uid), name="函数", subject="math",
                        difficulty_tier="blue", bloom_level="understand")
    sess = TrainingSession(user_id=uuid.UUID(uid), mode="compose", status="active",
                           question_count=1, answered_count=0)
    db.add_all([kp, sess])
    await db.commit()
    await db.refresh(kp)
    await db.refresh(sess)
    q = TrainingQuestion(
        session_id=sess.id, user_id=uuid.UUID(uid), knowledge_point_id=kp.id,
        bloom_level="understand", question_type="choice",
        question_text="1+1=?", reference_answer="2", user_answer=None, is_probe=False,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    async def _fake_grade(_self, _question, _ans):
        return (1.0, "正确", False, None)
    monkeypatch.setattr(type(training_service), "_grade_answer", _fake_grade)

    body = AnswerRequest(user_answer="2")
    await training_service.submit_answer(db, str(sess.id), str(q.id), uid, body)
    with pytest.raises(ValidationError):
        await training_service.submit_answer(db, str(sess.id), str(q.id), uid, body)

    await db.refresh(sess)
    assert sess.answered_count == 1  # 没有 +2


@pytest.mark.asyncio
async def test_studyspace_double_complete_awards_once(client: AsyncClient, db):
    uid = await _uid(client, db, "ss_dup@zhiyao.ai")
    chapter = CurriculumChapter(
        subject="math", grade_type="senior_high", grade_year=1, semester=1,
        chapter_index=1, chapter_title="第一章", lesson_index=1, lesson_title="函数",
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    ss = StudySpaceSession(user_id=uuid.UUID(uid), chapter_id=chapter.id,
                           status="active", session_type="lesson")
    db.add(ss)
    await db.commit()
    await db.refresh(ss)

    await studyspace_service.complete_session(db, uid, ss.id)
    with pytest.raises(AppError):
        await studyspace_service.complete_session(db, uid, ss.id)

    # 只发一次 30 星（无并发双发）
    awarded = (await db.execute(
        select(func.coalesce(func.sum(StarLedger.amount), 0)).where(
            StarLedger.user_id == uuid.UUID(uid),
            StarLedger.reason == "lesson_complete",
        )
    )).scalar_one()
    assert awarded == 30
