"""v0.28 RAG · Celery 嵌入流水线

异步把 KP / Note / CurriculumChapter 入库到 document_embeddings。
Q3 锁定：5min 延迟容忍，写入后排队，不阻塞主请求。
"""
import asyncio
import logging
import uuid

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.embedding_tasks.embed_kp", time_limit=120, soft_time_limit=100)
def embed_kp(kp_id: str):
    """单 KP 入库。KP 创建 / 更新时延迟 5min 触发。"""
    _run(_embed_kp_async(kp_id))


async def _embed_kp_async(kp_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.knowledge_point import KnowledgePoint
    from app.services.rag_service import upsert_doc

    async with AsyncSessionLocal() as db:
        kp = await db.get(KnowledgePoint, uuid.UUID(kp_id))
        if not kp:
            logger.warning(f"embed_kp: KP {kp_id} not found")
            return
        content = "\n".join(filter(None, [
            kp.name,
            kp.content or "",
            f"关键公式：{kp.key_formula}" if kp.key_formula else "",
        ]))
        await upsert_doc(
            db,
            doc_kind="kp",
            doc_id=kp.id,
            content=content,
            user_id=kp.user_id,
            project_id=kp.project_id,
            notebook_origin=kp.notebook_origin,
            metadata={
                "title": kp.name,
                "subject": kp.subject,
                "mastery_status": kp.mastery_status,
                "bloom_level": kp.bloom_level,
            },
        )
        logger.info(f"embed_kp: {kp_id} indexed")


@celery_app.task(name="app.tasks.embedding_tasks.embed_note", time_limit=180, soft_time_limit=160)
def embed_note(note_id: str):
    """笔记入库：用 exam_version（精简摘要）作为可检索摘要 + full_version 切块。"""
    _run(_embed_note_async(note_id))


async def _embed_note_async(note_id: str):
    from app.core.database import AsyncSessionLocal
    from app.models.note import Note
    from app.services.rag_service import upsert_doc

    async with AsyncSessionLocal() as db:
        note = await db.get(Note, uuid.UUID(note_id))
        if not note or note.status != "done":
            logger.info(f"embed_note: note {note_id} not ready (status={note.status if note else 'missing'})")
            return
        # chunk 0 = exam_version（高度浓缩，最适合作为 KP 级别召回）
        if note.exam_version:
            await upsert_doc(
                db,
                doc_kind="note",
                doc_id=note.id,
                chunk_index=0,
                content=f"{note.title}\n\n{note.exam_version}",
                user_id=note.user_id,
                project_id=note.project_id,
                notebook_origin=note.notebook_origin,
                metadata={
                    "title": note.title,
                    "subject": note.subject,
                    "chunk_kind": "exam_version",
                },
            )
        # chunk 1+ = full_version，按 ## 标题切块
        if note.full_version:
            chunks = _chunk_by_heading(note.full_version, max_chars=1200)
            for i, c in enumerate(chunks, start=1):
                await upsert_doc(
                    db,
                    doc_kind="note",
                    doc_id=note.id,
                    chunk_index=i,
                    content=f"{note.title} · 段{i}\n\n{c}",
                    user_id=note.user_id,
                    project_id=note.project_id,
                    notebook_origin=note.notebook_origin,
                    metadata={
                        "title": note.title,
                        "subject": note.subject,
                        "chunk_kind": "full_version",
                    },
                )
        logger.info(f"embed_note: {note_id} indexed")


def _chunk_by_heading(text: str, max_chars: int = 1200) -> list[str]:
    """按 ## / ### 切块；过长再按 max_chars 二次切。"""
    if not text:
        return []
    blocks: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if (line.startswith("## ") or line.startswith("### ")) and cur:
            blocks.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur).strip())
    # 二次切：超长 block 按 max_chars 硬切
    final: list[str] = []
    for b in blocks:
        if len(b) <= max_chars:
            final.append(b)
        else:
            for i in range(0, len(b), max_chars):
                final.append(b[i:i + max_chars])
    return [b for b in final if b.strip()]


@celery_app.task(name="app.tasks.embedding_tasks.embed_chapter")
def embed_chapter(chapter_id: str):
    """单课程章节入库（official content，user_id=NULL）"""
    _run(_embed_chapter_async(chapter_id))


async def _embed_chapter_async(chapter_id: str):
    from app.core.database import AsyncSessionLocal
    from app.models.curriculum import CurriculumChapter
    from app.services.rag_service import upsert_doc

    async with AsyncSessionLocal() as db:
        ch = await db.get(CurriculumChapter, uuid.UUID(chapter_id))
        if not ch:
            return
        content = f"{ch.subject} · {ch.chapter_title} · {ch.lesson_title}"
        await upsert_doc(
            db,
            doc_kind="chapter",
            doc_id=ch.id,
            content=content,
            user_id=None,
            project_id=None,
            notebook_origin="official",
            metadata={
                "title": ch.lesson_title,
                "subject": ch.subject,
                "is_key": ch.is_key,
                "grade_type": ch.grade_type,
                "chapter_title": ch.chapter_title,
            },
        )


@celery_app.task(name="app.tasks.embedding_tasks.backfill_user")
def backfill_user(user_id: str):
    """一次性把某用户所有 KP + Note 入库。冷启 / 上线后批量补齐。"""
    _run(_backfill_user_async(user_id))


async def _backfill_user_async(user_id: str):
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.knowledge_point import KnowledgePoint
    from app.models.note import Note

    async with AsyncSessionLocal() as db:
        uid = uuid.UUID(user_id)
        kp_ids = (await db.execute(select(KnowledgePoint.id).where(KnowledgePoint.user_id == uid))).scalars().all()
        note_ids = (await db.execute(
            select(Note.id).where(Note.user_id == uid, Note.status == "done")
        )).scalars().all()
    # 单独跑每条以复用 upsert 的 commit；可优化为批量。MVP 简洁优先。
    for kid in kp_ids:
        await _embed_kp_async(str(kid))
    for nid in note_ids:
        await _embed_note_async(str(nid))
    logger.info(f"backfill_user {user_id}: {len(kp_ids)} KPs + {len(note_ids)} notes")


@celery_app.task(name="app.tasks.embedding_tasks.backfill_official")
def backfill_official():
    """一次性把所有 curriculum_chapters 入库为 official content。"""
    _run(_backfill_official_async())


async def _backfill_official_async():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.curriculum import CurriculumChapter

    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(CurriculumChapter.id))).scalars().all()
    for cid in ids:
        await _embed_chapter_async(str(cid))
    logger.info(f"backfill_official: {len(ids)} chapters")
