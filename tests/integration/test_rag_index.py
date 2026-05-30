"""RAG 写入侧地基：统一索引入口 rag_index 与各写入路径的向量维护。"""
import uuid

import pytest

from app.models.document_embedding import DocumentEmbedding


def _add_vector(db, *, doc_kind: str, doc_id, user_id=None):
    # user_id 可空（official 内容用 NULL）；传 None 避免 users 外键约束
    db.add(
        DocumentEmbedding(
            user_id=user_id,
            doc_kind=doc_kind,
            doc_id=doc_id,
            chunk_index=0,
            content="x",
            embedding=[0.0] * 1024,
            doc_metadata={},
            embedding_model="bge-m3",
        )
    )


@pytest.mark.asyncio
async def test_enqueue_kp_index_schedules_celery(monkeypatch):
    from app.services import rag_index

    calls = {}

    def fake_apply_async(args=None, countdown=None, **kw):
        calls["args"] = args
        calls["countdown"] = countdown

    monkeypatch.setattr(
        "app.tasks.embedding_tasks.embed_kp.apply_async", fake_apply_async
    )
    rag_index.enqueue_kp_index("kp-1")
    assert calls["args"] == ["kp-1"]
    assert calls["countdown"] is not None


@pytest.mark.asyncio
async def test_enqueue_mistake_index_schedules_celery(monkeypatch):
    from app.services import rag_index

    calls = {}

    def fake_apply_async(args=None, countdown=None, **kw):
        calls["args"] = args

    monkeypatch.setattr(
        "app.tasks.embedding_tasks.embed_mistake.apply_async", fake_apply_async
    )
    rag_index.enqueue_mistake_index("q1")
    assert calls["args"] == ["q1"]


@pytest.mark.asyncio
async def test_purge_doc_deletes_vectors(db):
    from app.services import rag_index

    kp_id = uuid.uuid4()
    _add_vector(db, doc_kind="kp", doc_id=kp_id)
    await db.commit()

    removed = await rag_index.purge_doc(db, doc_kind="kp", doc_id=kp_id)
    assert removed >= 1

    # 再查应为空
    again = await rag_index.purge_doc(db, doc_kind="kp", doc_id=kp_id)
    assert again == 0


async def _register_user(client, email):
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    me = await client.get("/v1/auth/me", headers=h)
    return me.json()["data"]["id"]


@pytest.mark.asyncio
async def test_kp_create_triggers_index(client, db, monkeypatch):
    from app.services.knowledge_point_service import kp_service
    from app.schemas.knowledge_point import KnowledgePointCreate

    calls = []
    monkeypatch.setattr(
        "app.services.rag_index.enqueue_kp_index", lambda kp_id: calls.append(kp_id)
    )
    uid = await _register_user(client, "kp_idx_create@zhiyao.ai")
    kp = await kp_service.create(
        db, uid, KnowledgePointCreate(name="测试KP")
    )
    assert str(kp.id) in calls


@pytest.mark.asyncio
async def test_kp_update_triggers_reindex(client, db, monkeypatch):
    from app.services.knowledge_point_service import kp_service
    from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate

    calls = []

    async def fake_reindex(_db, kp_id):
        calls.append(kp_id)

    monkeypatch.setattr("app.services.rag_index.reindex_kp", fake_reindex)
    uid = await _register_user(client, "kp_idx_update@zhiyao.ai")
    kp = await kp_service.create(
        db, uid, KnowledgePointCreate(name="原KP")
    )
    await kp_service.update(
        db, str(kp.id), uid, KnowledgePointUpdate(content="更新内容")
    )
    assert str(kp.id) in calls


@pytest.mark.asyncio
async def test_kp_delete_purges_vectors(client, db):
    from app.services import rag_index
    from app.services.knowledge_point_service import kp_service
    from app.schemas.knowledge_point import KnowledgePointCreate

    uid = await _register_user(client, "kp_idx_delete@zhiyao.ai")
    kp = await kp_service.create(
        db, uid, KnowledgePointCreate(name="待删KP")
    )
    _add_vector(db, doc_kind="kp", doc_id=kp.id, user_id=uuid.UUID(uid))
    await db.commit()

    await kp_service.delete(db, str(kp.id), uid)

    remaining = await rag_index.purge_doc(db, doc_kind="kp", doc_id=kp.id)
    assert remaining == 0, "delete 后向量应已被失效，不应有残留"


@pytest.mark.asyncio
async def test_note_delete_purges_vectors(client, db):
    from app.services import rag_index
    from app.services.note_service import note_service
    from app.models.note import Note

    uid = await _register_user(client, "note_idx_delete@zhiyao.ai")
    note = Note(user_id=uuid.UUID(uid), source_type="text", title="待删笔记")
    db.add(note)
    await db.commit()
    await db.refresh(note)
    _add_vector(db, doc_kind="note", doc_id=note.id, user_id=uuid.UUID(uid))
    await db.commit()

    await note_service.delete_note(db, str(note.id), uid)

    remaining = await rag_index.purge_doc(db, doc_kind="note", doc_id=note.id)
    assert remaining == 0, "note 删除后向量应已失效"


@pytest.mark.asyncio
async def test_agent_create_kp_triggers_index(client, db, monkeypatch):
    from app.services import agent_tools

    calls = []
    monkeypatch.setattr(
        "app.services.rag_index.enqueue_kp_index", lambda kp_id: calls.append(kp_id)
    )
    uid = await _register_user(client, "agent_kp@zhiyao.ai")
    result = await agent_tools._manage_knowledge_points(
        db,
        uuid.UUID(uid),
        "create",
        new_kps=[{"title": "Agent建的KP", "subject": "math"}],
    )
    assert result["total"] == 1
    assert len(calls) == 1, "Agent 建 KP 应触发向量索引"


@pytest.mark.asyncio
async def test_submit_wrong_answer_enqueues_mistake(client, db, monkeypatch):
    """F 业务联动：答错训练题 → 错题入向量库；答对则不触发。"""
    import uuid as _uuid
    from app.services.knowledge_point_service import kp_service
    from app.schemas.knowledge_point import KnowledgePointCreate
    from app.services.training_service import training_service, TrainingService
    from app.models.training import TrainingSession, TrainingQuestion
    from app.schemas.training import AnswerRequest

    monkeypatch.setattr("app.services.rag_index.enqueue_kp_index", lambda x: None)
    uid = await _register_user(client, "mistake_trig@zhiyao.ai")
    uuid_uid = _uuid.UUID(uid)
    kp = await kp_service.create(db, uid, KnowledgePointCreate(name="测试KP"))

    async def _mk_question():
        sess = TrainingSession(
            user_id=uuid_uid, mode="single_kp", subject="math",
            question_count=1, status="active",
        )
        db.add(sess)
        await db.flush()
        q = TrainingQuestion(
            session_id=sess.id, user_id=uuid_uid, knowledge_point_id=kp.id,
            bloom_level="remember", question_type="short_answer",
            question_text="2+2=?", reference_answer="4",
        )
        db.add(q)
        await db.commit()
        return sess, q

    calls = []
    monkeypatch.setattr(
        "app.services.rag_index.enqueue_mistake_index", lambda qid: calls.append(qid)
    )

    # 答错 → 触发
    async def grade_wrong(self, question, user_answer):
        return (0.0, "错了", True, "concept")

    monkeypatch.setattr(TrainingService, "_grade_answer", grade_wrong)
    sess, q = await _mk_question()
    await training_service.submit_answer(
        db, str(sess.id), str(q.id), uid, AnswerRequest(user_answer="5")
    )
    assert str(q.id) in calls, "答错应触发错题入向量库"

    # 答对 → 不触发
    calls.clear()

    async def grade_right(self, question, user_answer):
        return (1.0, "对", False, None)

    monkeypatch.setattr(TrainingService, "_grade_answer", grade_right)
    sess2, q2 = await _mk_question()
    await training_service.submit_answer(
        db, str(sess2.id), str(q2.id), uid, AnswerRequest(user_answer="4")
    )
    assert str(q2.id) not in calls, "答对不应触发"


@pytest.mark.asyncio
async def test_diagnose_returns_recent_mistakes(client, db, monkeypatch):
    """诊断增强：返回具体错题样本（DB query，精确全量——不是 RAG 语义场景）。"""
    import uuid as _uuid
    from datetime import datetime, timezone
    from app.services import agent_tools
    from app.services.knowledge_point_service import kp_service
    from app.schemas.knowledge_point import KnowledgePointCreate
    from app.models.training import TrainingSession, TrainingQuestion

    monkeypatch.setattr("app.services.rag_index.enqueue_kp_index", lambda x: None)
    uid = await _register_user(client, "diag_mistake@zhiyao.ai")
    uuid_uid = _uuid.UUID(uid)
    kp = await kp_service.create(db, uid, KnowledgePointCreate(name="导数KP", subject="math"))
    sess = TrainingSession(
        user_id=uuid_uid, mode="single_kp", subject="math",
        question_count=1, status="completed",
    )
    db.add(sess)
    await db.flush()
    q = TrainingQuestion(
        session_id=sess.id, user_id=uuid_uid, knowledge_point_id=kp.id,
        bloom_level="remember", question_type="short_answer",
        question_text="求 2x 的导数", reference_answer="2", is_wrong=True,
        error_reason="concept", answered_at=datetime.now(timezone.utc),
    )
    db.add(q)
    await db.commit()

    result = await agent_tools._diagnose_learning(db, uuid_uid, subject="math")
    assert "recent_mistakes" in result
    qs = [m["question"] for m in result["recent_mistakes"]]
    assert any("求 2x 的导数" in t for t in qs)
    assert result["recent_mistakes"][0]["error_reason"] == "concept"


@pytest.mark.asyncio
async def test_admin_backfill_requires_admin(client):
    resp = await client.post("/admin/rag/backfill/some-user-id")
    assert resp.status_code in (401, 403)
