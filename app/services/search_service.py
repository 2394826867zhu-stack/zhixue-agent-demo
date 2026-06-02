"""C-09 全局搜索聚合 service。

跨 flashcard / note / knowledge_point / mistake(错题) / project 五类资源做 ILIKE 模糊搜索，
全部按 user_id 隔离，统一成 SearchResultItem 形状。纯 ILIKE（PostgreSQL 原生，支持中文），
未来可按需升级 GIN 全文索引。搜索风格对齐 agent_history_service。
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import Flashcard
from app.models.note import Note
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion
from app.models.project import Project

ALL_TYPES = ("flashcard", "note", "knowledge_point", "mistake", "project")


def _snippet(text: str | None, limit: int = 80) -> str | None:
    """把多行文本压成单行摘录，超长截断加省略号。空 → None。"""
    if not text:
        return None
    t = " ".join(str(text).split())
    if not t:
        return None
    return t[:limit] + ("…" if len(t) > limit else "")


async def aggregate_search(
    db: AsyncSession,
    user_id: str,
    query: str,
    *,
    types: list[str] | None = None,
    limit_per_type: int = 5,
) -> dict:
    """跨 5 表 ILIKE 聚合搜索（user_id 隔离），按 created_at 倒序混合。"""
    q = (query or "").strip()
    if not q:
        return {"query": query, "items": [], "total": 0}

    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    like = f"%{q}%"
    sel = set(types) if types else set(ALL_TYPES)
    items: list[dict] = []

    if "flashcard" in sel:
        rows = (await db.execute(
            select(Flashcard).where(
                Flashcard.user_id == uid,
                or_(Flashcard.front.ilike(like), Flashcard.back.ilike(like)),
            ).order_by(Flashcard.created_at.desc()).limit(limit_per_type)
        )).scalars().all()
        items += [{
            "type": "flashcard", "id": c.id,
            "title": _snippet(c.front, 40) or "闪卡",
            "snippet": _snippet(c.back), "subject": getattr(c, "subject", None),
            "created_at": c.created_at,
        } for c in rows]

    if "note" in sel:
        rows = (await db.execute(
            select(Note).where(
                Note.user_id == uid,
                or_(Note.title.ilike(like), Note.full_version.ilike(like), Note.source_input.ilike(like)),
            ).order_by(Note.created_at.desc()).limit(limit_per_type)
        )).scalars().all()
        items += [{
            "type": "note", "id": n.id,
            "title": n.title or "笔记",
            "snippet": _snippet(n.full_version or n.source_input),
            "subject": getattr(n, "subject", None), "created_at": n.created_at,
        } for n in rows]

    if "knowledge_point" in sel:
        rows = (await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.user_id == uid,
                or_(KnowledgePoint.name.ilike(like), KnowledgePoint.content.ilike(like)),
            ).order_by(KnowledgePoint.created_at.desc()).limit(limit_per_type)
        )).scalars().all()
        items += [{
            "type": "knowledge_point", "id": k.id,
            "title": k.name, "snippet": _snippet(k.content),
            "subject": getattr(k, "subject", None), "created_at": k.created_at,
        } for k in rows]

    if "mistake" in sel:
        rows = (await db.execute(
            select(TrainingQuestion).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong.is_(True),
                or_(TrainingQuestion.question_text.ilike(like), TrainingQuestion.reference_answer.ilike(like)),
            ).order_by(TrainingQuestion.created_at.desc()).limit(limit_per_type)
        )).scalars().all()
        items += [{
            "type": "mistake", "id": m.id,
            "title": _snippet(m.question_text, 40) or "错题",
            "snippet": _snippet(m.reference_answer),
            "subject": getattr(m, "subject", None), "created_at": m.created_at,
        } for m in rows]

    if "project" in sel:
        rows = (await db.execute(
            select(Project).where(
                Project.user_id == uid,
                or_(Project.name.ilike(like), Project.summary.ilike(like)),
            ).order_by(Project.created_at.desc()).limit(limit_per_type)
        )).scalars().all()
        items += [{
            "type": "project", "id": p.id,
            "title": p.name, "snippet": _snippet(p.summary),
            "subject": getattr(p, "subject", None), "created_at": p.created_at,
        } for p in rows]

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"query": q, "items": items, "total": len(items)}
