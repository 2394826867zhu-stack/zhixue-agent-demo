import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import ValidationError
from app.models.knowledge_point import KnowledgePoint
from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteUploadRequest
from app.services.note_service import note_service
from app.tasks import note_tasks


@pytest.mark.asyncio
async def test_process_note_does_not_process_note_for_wrong_user(db, monkeypatch):
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    db.add_all(
        [
            User(id=owner_id, email=f"{owner_id}@example.com", password_hash="test-hash"),
            User(id=other_id, email=f"{other_id}@example.com", password_hash="test-hash"),
        ]
    )
    await db.flush()
    note = Note(
        user_id=owner_id,
        title="所有权测试",
        subject="数学",
        source_type="text",
        source_input="函数与导数",
        status="processing",
    )
    db.add(note)
    await db.commit()

    async def noop_progress(*args, **kwargs):
        return None

    async def fake_generate(*args, **kwargs):
        return '{"title":"测试","subject":"数学","core_content":"内容","knowledge_points":[{"name":"导数","content":"内容","bloom_level":"remember"}],"difficulty_points":[],"key_formulas":[]}'

    class TestSessionFactory:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def session_factory():
        return TestSessionFactory()

    monkeypatch.setattr("app.core.database.AsyncSessionLocal", session_factory)
    monkeypatch.setattr(note_tasks, "_update_task_progress", noop_progress)
    monkeypatch.setattr("app.llm.client.llm_client.generate", fake_generate)

    await note_tasks._process_note_async(None, str(note.id), str(other_id))

    rows = await db.execute(select(KnowledgePoint).where(KnowledgePoint.note_id == note.id))
    assert rows.scalars().all() == []


@pytest.mark.asyncio
async def test_failed_note_task_status_reports_failure(db, monkeypatch):
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test-hash"))
    await db.flush()
    note = Note(user_id=user_id, title="失败笔记", source_type="text", source_input="x", status="failed")
    db.add(note)
    await db.commit()

    class EmptyRedis:
        async def hgetall(self, key):
            return {}

    async def fake_get_redis():
        return EmptyRedis()

    monkeypatch.setattr("app.services.note_service.get_redis", fake_get_redis)

    status = await note_service.get_task_status(str(note.id), str(user_id), db)

    assert status["status"] == "failed"
    assert status["progress"] == 100
    assert "失败" in status["message"]


@pytest.mark.asyncio
async def test_pdf_without_extractable_text_is_rejected(db, monkeypatch):
    user_id = uuid.uuid4()
    db.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test-hash"))
    await db.commit()

    monkeypatch.setattr("app.services.note_service._extract_pdf_text", lambda *args, **kwargs: "")

    with pytest.raises(ValidationError):
        await note_service.create_from_file(
            db,
            str(user_id),
            b"%PDF-1.4\n%%EOF",
            "application/pdf",
            "empty.pdf",
        )
