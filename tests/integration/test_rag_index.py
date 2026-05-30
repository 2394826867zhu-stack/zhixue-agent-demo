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
