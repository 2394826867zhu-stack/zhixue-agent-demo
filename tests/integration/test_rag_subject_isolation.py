"""F6b（v3）: RAG 官方内容跨科隔离 —— 修教学串科（德语讲成英语主旨大意）。

根因:旧 subject 过滤 `subject=:subj OR subject IS NULL` 对官方内容也放行无标签 → 无 subject
标签的官方英语章节命中德语 query。修复:官方内容严格 subject 匹配（无 NULL 逃逸），无标签
放行只留给用户自己的内容。
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.user import User
from app.models.document_embedding import DocumentEmbedding
from app.config import settings
from app.services import rag_service


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_official_subject_strict_no_cross_subject(client: AsyncClient, db: AsyncSession, monkeypatch):
    vec = [0.1] * 1024  # 固定向量 → 所有行等距,纯由 subject 过滤决定召回（确定性,不跑 BGE-M3）
    async def _fake_embed(_text):
        return vec
    monkeypatch.setattr("app.services.rag_service.embed_text", _fake_embed)

    await _auth(client, "ragiso@zhiyao.ai")
    uid = (await db.execute(select(User).where(User.email == "ragiso@zhiyao.ai"))).scalar_one().id

    def emb(user_id, subject, content, kind):
        return DocumentEmbedding(
            user_id=user_id, doc_kind=kind, doc_id=uuid.uuid4(),
            content=content, embedding=vec, embedding_model=settings.EMBEDDING_MODEL,
            doc_metadata=({"subject": subject} if subject else {}),
        )
    db.add(emb(None, "英语", "主旨大意题解法", "chapter"))   # 官方英语（有标签）
    db.add(emb(None, None, "无标签官方章节", "chapter"))      # 官方无标签
    db.add(emb(uid, "德语", "德语字母与发音", "kp"))          # 用户自己的德语
    db.add(emb(uid, None, "我未标注的笔记", "note"))          # 用户自己无标签
    await db.commit()

    hits = await rag_service.search(
        db, user_id=uid, query="德语怎么发音", top_k=20,
        doc_kinds=["kp", "note", "chapter"], include_official=True, subject="德语",
    )
    contents = {h["content"] for h in hits}

    # 官方内容严格按 subject：英语/无标签官方都不得串入德语 query
    assert "主旨大意题解法" not in contents, "官方英语内容串科了"
    assert "无标签官方章节" not in contents, "无标签官方内容串科了"
    # 用户自己的内容宽松：德语 + 自己未标注的都召回
    assert "德语字母与发音" in contents, "用户自己的德语内容应召回"
    assert "我未标注的笔记" in contents, "用户自己未标注内容应召回（宽松）"
