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
