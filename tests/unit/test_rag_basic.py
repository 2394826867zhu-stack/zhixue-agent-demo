"""v0.28 RAG MVP · 基础测试

策略：mock embedding_service 返回确定性 fake 向量（避免下 1.3GB BGE-M3）
验证：upsert + search + 用户隔离 + official 召回
"""
import uuid
import pytest
import pytest_asyncio
from unittest.mock import patch

from app.services import rag_service, embedding_service
from app.config import settings


def _fake_vec(seed: int) -> list[float]:
    """生成确定性的 1024 维归一化向量"""
    import math
    raw = [(seed * (i + 1)) % 100 / 100.0 for i in range(settings.EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


@pytest_asyncio.fixture
async def patched_embed():
    """全局 patch embedding_service.embed_text/embed_batch 返回 fake 向量"""
    # 用每次调用文本的 hash 作为 seed —— 同样文本同样向量
    async def fake_embed_text(text: str):
        seed = abs(hash(text)) % 1000
        return _fake_vec(seed)

    async def fake_embed_batch(texts, batch_size=16):
        return [await fake_embed_text(t) for t in texts]

    with patch.object(embedding_service, "embed_text", side_effect=fake_embed_text), \
         patch.object(embedding_service, "embed_batch", side_effect=fake_embed_batch), \
         patch.object(rag_service, "embed_text", side_effect=fake_embed_text), \
         patch.object(rag_service, "embed_batch", side_effect=fake_embed_batch):
        yield


@pytest.mark.asyncio
async def test_upsert_and_search_user_isolation(db, patched_embed):
    """两个用户分别 upsert，互相不能召回对方的"""
    from app.models.user import User
    from app.core.security import hash_password

    u1 = User(email="u1@test.com", password_hash=hash_password("x"), nickname="u1")
    u2 = User(email="u2@test.com", password_hash=hash_password("x"), nickname="u2")
    db.add_all([u1, u2])
    await db.commit()
    await db.refresh(u1)
    await db.refresh(u2)

    # u1 写 1 条 KP，u2 写 1 条
    await rag_service.upsert_doc(
        db, doc_kind="kp", doc_id=uuid.uuid4(),
        content="导数的几何意义就是切线斜率", user_id=u1.id,
        metadata={"title": "导数几何意义", "subject": "数学"},
    )
    await rag_service.upsert_doc(
        db, doc_kind="kp", doc_id=uuid.uuid4(),
        content="化学键能反映分子稳定性", user_id=u2.id,
        metadata={"title": "化学键能", "subject": "化学"},
    )

    # u1 搜 "导数" 应只看到自己的，u2 搜应只看到化学
    r1 = await rag_service.search(db, user_id=u1.id, query="导数的几何意义就是切线斜率", top_k=5)
    r2 = await rag_service.search(db, user_id=u2.id, query="化学键能反映分子稳定性", top_k=5)

    assert len(r1) == 1, f"u1 应只召回自己 1 条，实际 {len(r1)}"
    assert r1[0]["metadata"]["subject"] == "数学"
    assert len(r2) == 1
    assert r2[0]["metadata"]["subject"] == "化学"


@pytest.mark.asyncio
async def test_official_content_visible_to_all(db, patched_embed):
    """user_id IS NULL（official content）可被所有用户召回"""
    from app.models.user import User
    from app.core.security import hash_password

    u = User(email="u@test.com", password_hash=hash_password("x"), nickname="u")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    # 写一条 official chapter（user_id=None）
    await rag_service.upsert_doc(
        db, doc_kind="chapter", doc_id=uuid.uuid4(),
        content="高中数学 · 导数与微分",
        user_id=None, notebook_origin="official",
        metadata={"title": "导数与微分", "subject": "数学"},
    )
    hits = await rag_service.search(
        db, user_id=u.id, query="高中数学 · 导数与微分", top_k=5, include_official=True,
    )
    assert len(hits) == 1
    assert hits[0]["doc_kind"] == "chapter"


@pytest.mark.asyncio
async def test_doc_kind_filter(db, patched_embed):
    """doc_kinds 过滤生效"""
    from app.models.user import User
    from app.core.security import hash_password

    u = User(email="x@test.com", password_hash=hash_password("x"), nickname="x")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    same_content = "三角函数的周期性"
    await rag_service.upsert_doc(
        db, doc_kind="kp", doc_id=uuid.uuid4(), content=same_content, user_id=u.id,
    )
    await rag_service.upsert_doc(
        db, doc_kind="note", doc_id=uuid.uuid4(), content=same_content, user_id=u.id,
    )

    only_kp = await rag_service.search(db, user_id=u.id, query=same_content, doc_kinds=["kp"])
    assert len(only_kp) == 1
    assert only_kp[0]["doc_kind"] == "kp"


@pytest.mark.asyncio
async def test_upsert_idempotent_on_conflict(db, patched_embed):
    """同 (doc_kind, doc_id, chunk, model) → 第二次 upsert 走 conflict_update"""
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select, func
    from app.models.document_embedding import DocumentEmbedding

    u = User(email="i@test.com", password_hash=hash_password("x"), nickname="i")
    db.add(u)
    await db.commit()
    await db.refresh(u)

    did = uuid.uuid4()
    await rag_service.upsert_doc(db, doc_kind="kp", doc_id=did, content="v1", user_id=u.id)
    await rag_service.upsert_doc(db, doc_kind="kp", doc_id=did, content="v2", user_id=u.id)

    cnt = (await db.execute(
        select(func.count()).where(DocumentEmbedding.doc_id == did)
    )).scalar_one()
    assert cnt == 1, f"应只有 1 行，实际 {cnt}"

    # 第二次的 content 应该是 v2
    row = (await db.execute(
        select(DocumentEmbedding).where(DocumentEmbedding.doc_id == did)
    )).scalar_one()
    assert row.content == "v2"


@pytest.mark.asyncio
async def test_format_for_prompt():
    """format_for_prompt 输出引用块"""
    hits = [
        {"doc_kind": "kp", "doc_id": "x", "content": "导数定义", "metadata": {"title": "导数", "subject": "数学"}, "score": 0.9, "id": "1", "chunk_index": 0},
        {"doc_kind": "note", "doc_id": "y", "content": "笔记内容", "metadata": {"title": "微积分笔记"}, "score": 0.8, "id": "2", "chunk_index": 0},
    ]
    block = rag_service.format_for_prompt(hits)
    assert "[1]" in block
    assert "[2]" in block
    assert "导数" in block
    assert "笔记" in block


@pytest.mark.asyncio
async def test_format_for_prompt_empty():
    assert rag_service.format_for_prompt([]) == ""
