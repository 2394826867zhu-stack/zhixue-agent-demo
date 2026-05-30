"""v0.28 RAG · 检索服务

upsert / search / 用户范围隔离。

Q1 锁定：仅检索用户自己的 KP/notes（user_id 强过滤）
Q2 锁定：subject 严格隔离（可选 by metadata.subject）
Q3 锁定：Celery 异步重建 5min 延迟（参 tasks/embedding_tasks.py）
"""
import logging
import uuid
from typing import Any

from sqlalchemy import select, delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document_embedding import DocumentEmbedding
from app.services.embedding_service import embed_text, embed_batch

logger = logging.getLogger(__name__)

# 检索 top-K 默认值
DEFAULT_TOP_K = 5
SEARCH_TOP_K_CAP = 30  # 最多召回 30 再 filter


async def upsert_doc(
    db: AsyncSession,
    *,
    doc_kind: str,
    doc_id: uuid.UUID,
    content: str,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    notebook_origin: str | None = None,
    chunk_index: int = 0,
    metadata: dict | None = None,
) -> uuid.UUID:
    """Upsert 单条文档 chunk → 向量化 → 写表（按 doc_kind+doc_id+chunk+model 唯一）"""
    vec = await embed_text(content)
    return await _persist_one(
        db,
        doc_kind=doc_kind,
        doc_id=doc_id,
        content=content,
        embedding=vec,
        user_id=user_id,
        project_id=project_id,
        notebook_origin=notebook_origin,
        chunk_index=chunk_index,
        metadata=metadata or {},
    )


async def upsert_batch(
    db: AsyncSession,
    items: list[dict],
) -> int:
    """批量 upsert。items 每项 dict: {doc_kind, doc_id, content, user_id?, project_id?, notebook_origin?, chunk_index?, metadata?}"""
    if not items:
        return 0
    contents = [it["content"] for it in items]
    vecs = await embed_batch(contents)
    count = 0
    for it, vec in zip(items, vecs):
        await _persist_one(
            db,
            doc_kind=it["doc_kind"],
            doc_id=it["doc_id"],
            content=it["content"],
            embedding=vec,
            user_id=it.get("user_id"),
            project_id=it.get("project_id"),
            notebook_origin=it.get("notebook_origin"),
            chunk_index=it.get("chunk_index", 0),
            metadata=it.get("metadata") or {},
            commit=False,
        )
        count += 1
    await db.commit()
    return count


async def _persist_one(
    db: AsyncSession,
    *,
    doc_kind: str,
    doc_id: uuid.UUID,
    content: str,
    embedding: list[float],
    user_id: uuid.UUID | None,
    project_id: uuid.UUID | None,
    notebook_origin: str | None,
    chunk_index: int,
    metadata: dict,
    commit: bool = True,
) -> uuid.UUID:
    stmt = pg_insert(DocumentEmbedding).values(
        user_id=user_id,
        project_id=project_id,
        notebook_origin=notebook_origin,
        doc_kind=doc_kind,
        doc_id=doc_id,
        chunk_index=chunk_index,
        content=content,
        embedding=embedding,
        doc_metadata=metadata,
        embedding_model=settings.EMBEDDING_MODEL,
        embedding_version=settings.EMBEDDING_PROVIDER,
    ).on_conflict_do_update(
        constraint="uq_doc_embed_identity",
        set_={
            "content": content,
            "embedding": embedding,
            "doc_metadata": metadata,
            "user_id": user_id,
            "project_id": project_id,
            "notebook_origin": notebook_origin,
            "updated_at": text("now()"),
        },
    ).returning(DocumentEmbedding.id)
    res = await db.execute(stmt)
    row = res.fetchone()
    if commit:
        await db.commit()
    return row[0] if row else doc_id


async def search(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    doc_kinds: list[str] | None = None,
    project_id: uuid.UUID | None = None,
    include_official: bool = True,
    subject: str | None = None,
    org_id: uuid.UUID | None = None,
) -> list[dict]:
    """语义检索 top-K。

    返回 list[{id, doc_kind, doc_id, content, score, metadata, chunk_index}]，score ∈ [0,1] 越大越相似。
    """
    if not query or not query.strip():
        return []
    query_vec = await embed_text(query)

    # 构造 SQL：用 pgvector <=> 算 cosine distance（0..2，越小越相似）；score = 1 - distance
    # 用户隔离：(user_id = me) OR (include_official AND user_id IS NULL)
    sql = """
        SELECT id, doc_kind, doc_id, chunk_index, content, doc_metadata,
               1 - (embedding <=> CAST(:qvec AS vector)) AS score
        FROM document_embeddings
        WHERE embedding_model = :model
          AND (
            user_id = :uid
            {org_clause}
            {official_clause}
          )
          {kind_clause}
          {project_clause}
          {subject_clause}
        ORDER BY embedding <=> CAST(:qvec AS vector)
        LIMIT :k
    """
    params: dict[str, Any] = {
        "qvec": str(query_vec),
        "model": settings.EMBEDDING_MODEL,
        "uid": user_id,
        "k": min(top_k, SEARCH_TOP_K_CAP),
    }
    # 三级隔离：self（user_id=me）/ tenant（org_id=我的机构共享库）/ official（两者皆 NULL）
    org_clause = "OR org_id = :org_id" if org_id is not None else ""
    if org_id is not None:
        params["org_id"] = org_id
    official_clause = "OR (user_id IS NULL AND org_id IS NULL)" if include_official else ""
    kind_clause = ""
    if doc_kinds:
        kind_clause = "AND doc_kind = ANY(:kinds)"
        params["kinds"] = doc_kinds
    project_clause = ""
    if project_id is not None:
        project_clause = "AND (project_id = :pid OR project_id IS NULL)"
        params["pid"] = project_id
    subject_clause = ""
    if subject:
        subject_clause = "AND (doc_metadata->>'subject' = :subj OR doc_metadata->>'subject' IS NULL)"
        params["subj"] = subject

    sql_final = sql.format(
        org_clause=org_clause,
        official_clause=official_clause,
        kind_clause=kind_clause,
        project_clause=project_clause,
        subject_clause=subject_clause,
    )
    res = await db.execute(text(sql_final), params)
    rows = res.fetchall()
    out = []
    for r in rows:
        out.append({
            "id": str(r.id),
            "doc_kind": r.doc_kind,
            "doc_id": str(r.doc_id),
            "chunk_index": r.chunk_index,
            "content": r.content,
            "score": float(r.score) if r.score is not None else 0.0,
            "metadata": dict(r.doc_metadata or {}),
        })
    return out


async def delete_doc(
    db: AsyncSession,
    *,
    doc_kind: str,
    doc_id: uuid.UUID,
) -> int:
    """删除某文档的所有 chunk 向量（用户改 KP/note 时调用）"""
    res = await db.execute(
        delete(DocumentEmbedding).where(
            DocumentEmbedding.doc_kind == doc_kind,
            DocumentEmbedding.doc_id == doc_id,
        )
    )
    await db.commit()
    return res.rowcount or 0


_KIND_LABEL = {
    "kp": "知识点", "note": "笔记", "chapter": "课程",
    "mistake": "错题", "episode": "记忆", "guidance": "引导",
}


def format_citations(hits: list[dict]) -> list[dict]:
    """把 RAG 召回结果格式化为前端可展示的引用来源列表（C-12 引用展示契约）。"""
    out = []
    for h in hits:
        meta = h.get("metadata") or {}
        kind = h.get("doc_kind")
        out.append({
            "doc_kind": kind,
            "source_label": _KIND_LABEL.get(kind, kind),
            "title": meta.get("title") or (h.get("content", "")[:30]),
            "score": h.get("score", 0.0),
            "doc_id": h.get("doc_id"),
        })
    return out


def summarize_retrieval(query: str, hits: list[dict]) -> dict:
    """把一次 RAG 召回压缩成可观测指标（E 可观测·召回质量埋点）。

    不落原始 query（隐私），只记长度；统计命中数 / score 分布 / doc_kind 分布 /
    零召回标记。供结构化日志与离线分析，数据驱动后续检索与上下文迭代。
    """
    scores = [h.get("score", 0.0) for h in hits if h.get("score") is not None]
    kind_dist: dict[str, int] = {}
    for h in hits:
        k = h.get("doc_kind") or "unknown"
        kind_dist[k] = kind_dist.get(k, 0) + 1
    return {
        "query_len": len(query or ""),
        "hit_count": len(hits),
        "is_empty": len(hits) == 0,
        "score_max": max(scores) if scores else None,
        "score_min": min(scores) if scores else None,
        "score_avg": (sum(scores) / len(scores)) if scores else None,
        "kind_distribution": kind_dist,
    }


def format_for_prompt(hits: list[dict]) -> str:
    """把检索结果格式化为可拼进 system prompt 的引用块。"""
    if not hits:
        return ""
    lines = ["## 相关学习内容（来自你的笔记/知识点/课程）"]
    for i, h in enumerate(hits, 1):
        kind_label = {
            "kp": "知识点",
            "note": "笔记",
            "chapter": "课程章节",
            "guidance": "引导对话",
            "episode": "历史事件",
        }.get(h["doc_kind"], h["doc_kind"])
        title = h["metadata"].get("title") or h["metadata"].get("name") or ""
        snippet = (h["content"] or "")[:280].replace("\n", " ")
        head = f"[{i}] {kind_label}"
        if title:
            head += f" · {title}"
        lines.append(f"{head}\n{snippet}")
    lines.append(
        "\n以上是基于用户当前消息检索到的相关学习材料。可在回答时参考；"
        "若提到具体内容，可用 [1][2] 形式标注来源。不要无依据编造。"
    )
    return "\n\n".join(lines)
