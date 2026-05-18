import uuid
from datetime import date

import pytest

from app.core.exceptions import PermissionDeniedError
from app.core.exceptions import NotFoundError, LLMError
from app.models.exam import Exam
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion
from app.models.user import User
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate
from app.services.exam_service import exam_service
from app.services.knowledge_point_service import kp_service
from app.services.mistake_service import mistake_service


@pytest.mark.asyncio
async def test_exam_cross_user_update_raises_permission_denied(db):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    db.add_all(
        [
            User(id=owner_id, email=f"{owner_id}@example.com", password_hash="test-hash"),
            User(id=other_id, email=f"{other_id}@example.com", password_hash="test-hash"),
        ]
    )
    await db.flush()
    exam = Exam(user_id=owner_id, name="期末考试", subject="数学", exam_date=date(2026, 6, 20))
    db.add(exam)
    await db.commit()

    with pytest.raises(PermissionDeniedError):
        await exam_service.update_exam(db, str(exam.id), str(other_id), data={})


@pytest.mark.asyncio
async def test_create_knowledge_point_rejects_missing_chapter(db):
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test-hash"))
    await db.commit()

    with pytest.raises(NotFoundError):
        await kp_service.create(
            db,
            str(user_id),
            KnowledgePointCreate(name="不存在章节", chapter_id=uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_update_knowledge_point_rejects_missing_chapter(db):
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test-hash"))
    await db.flush()
    kp = await kp_service.create(db, str(user_id), KnowledgePointCreate(name="函数"))

    with pytest.raises(NotFoundError):
        await kp_service.update(
            db,
            str(kp.id),
            str(user_id),
            KnowledgePointUpdate(chapter_id=uuid.uuid4()),
        )


@pytest.mark.asyncio
async def test_create_retry_returns_llm_error_when_generation_fails(db, monkeypatch):
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test-hash"))
    await db.flush()
    kp = KnowledgePoint(user_id=user_id, name="函数", subject="数学", bloom_level="understand")
    db.add(kp)
    await db.flush()
    question = TrainingQuestion(
        user_id=user_id,
        knowledge_point_id=kp.id,
        bloom_level="understand",
        question_type="essay",
        question_text="解释函数单调性",
        reference_answer="略",
        is_wrong=True,
    )
    db.add(question)
    await db.commit()

    async def fail_generate(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("app.llm.client.llm_client.generate", fail_generate)

    with pytest.raises(LLMError):
        await mistake_service.create_retry(db, str(question.id), str(user_id))
