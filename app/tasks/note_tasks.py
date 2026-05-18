import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    """在 Celery 同步上下文中运行异步函数。
    每次调用前清理全局连接池（asyncpg + aioredis），
    避免跨 event loop 复用旧连接时报错。
    """
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None  # 强制下次 get_redis() 创建新连接
    return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_note(self, note_id: str, user_id: str):
    """
    笔记处理主任务：提取内容 → 并行生成三件套 → 写入知识点
    """
    try:
        _run(_process_note_async(self, note_id, user_id))
    except Exception as exc:
        logger.error(f"Note task failed for {note_id}: {exc}")
        try:
            _run(_mark_note_failed(note_id, str(exc)))
        except Exception as mark_err:
            logger.error(f"Failed to mark note {note_id} as failed: {mark_err}")
        raise self.retry(exc=exc)


async def _process_note_async(task, note_id: str, user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.models.note import Note
    from app.llm.client import llm_client
    from app.llm.prompts.note_prompts import (
        SYSTEM_NOTE, EXTRACT_FROM_AI, EXTRACT_FROM_CONTENT,
        FULL_VERSION_PROMPT, EXAM_VERSION_PROMPT, GRAPH_MERMAID_PROMPT,
    )
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Note).where(
                Note.id == uuid.UUID(note_id),
                Note.user_id == uuid.UUID(user_id),
            )
        )
        note = result.scalar_one_or_none()
        if not note:
            logger.error(f"Note {note_id} not found for user {user_id}")
            return

        await _update_task_progress(note_id, 10, "正在理解内容...")

        # Step 1: 提取结构化内容
        if note.source_type == "ai_generated":
            prompt = EXTRACT_FROM_AI.format(topic=note.source_input)
            raw = await llm_client.generate(prompt, system=SYSTEM_NOTE)
        else:
            content = note.source_input or ""
            prompt = EXTRACT_FROM_CONTENT.format(content=content)
            image_b64 = None
            if note.source_file_url and note.source_type == "image":
                image_b64 = _load_image_b64(note.source_file_url)
            raw = await llm_client.generate(prompt, system=SYSTEM_NOTE, image_b64=image_b64)

        extracted = _parse_json_safe(raw)
        if not extracted:
            raise ValueError("内容提取失败，LLM未返回有效JSON")

        await _update_task_progress(note_id, 30, "正在生成精读版...")

        # Step 2: 并行生成三件套
        core_content = extracted.get("core_content", "")
        key_formulas = "、".join(extracted.get("key_formulas", []))
        kp_names = "、".join(kp["name"] for kp in extracted.get("knowledge_points", []))

        full_v, exam_v, graph_v = await asyncio.gather(
            llm_client.generate(FULL_VERSION_PROMPT.format(core_content=core_content), system=SYSTEM_NOTE),
            llm_client.generate(EXAM_VERSION_PROMPT.format(core_content=core_content, key_formulas=key_formulas), system=SYSTEM_NOTE),
            llm_client.generate(GRAPH_MERMAID_PROMPT.format(knowledge_points_names=kp_names, title=extracted.get("title", "")), system=SYSTEM_NOTE),
        )

        await _update_task_progress(note_id, 75, "正在提取知识点...")

        # Step 3: 更新笔记
        note.title = note.title or extracted.get("title", "")
        note.subject = note.subject or extracted.get("subject", "other")
        note.full_version = full_v
        note.exam_version = exam_v
        note.graph_mermaid = _clean_mermaid(graph_v)
        note.difficulty_points = extracted.get("difficulty_points", [])
        note.status = "done"
        note.updated_at = datetime.now(timezone.utc)

        # Step 4: 写入知识点（先删旧数据保证 retry 幂等）
        from app.models.knowledge_point import KnowledgePoint
        from sqlalchemy import delete as sa_delete
        await db.execute(
            sa_delete(KnowledgePoint).where(
                KnowledgePoint.note_id == uuid.UUID(note_id),
                KnowledgePoint.user_id == uuid.UUID(user_id),
            )
        )
        for kp_data in extracted.get("knowledge_points", []):
            kp = KnowledgePoint(
                user_id=uuid.UUID(user_id),
                note_id=uuid.UUID(note_id),
                name=kp_data.get("name", ""),
                subject=note.subject,
                content=kp_data.get("content", ""),
                key_formula=kp_data.get("key_formula") or None,
                bloom_level=kp_data.get("bloom_level", "remember"),
                mastery_status="new",
            )
            db.add(kp)

        await db.commit()
        await _update_task_progress(note_id, 100, "完成")
        logger.info(f"Note {note_id} processed successfully")


async def _update_task_progress(note_id: str, progress: int, message: str):
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.hset(f"note_task:{note_id}", "progress", progress)
    await redis.hset(f"note_task:{note_id}", "message", message)
    await redis.expire(f"note_task:{note_id}", 3600)


async def _mark_note_failed(note_id: str, error: str):
    from app.core.database import AsyncSessionLocal
    from app.models.note import Note
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Note).where(Note.id == uuid.UUID(note_id)))
        note = result.scalar_one_or_none()
        if note:
            note.status = "failed"
            await db.commit()


def _load_image_b64(file_url: str) -> str | None:
    import base64, os
    try:
        if os.path.exists(file_url):
            with open(file_url, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"Failed to load image {file_url}: {e}")
    return None


def _parse_json_safe(text: str) -> dict | None:
    try:
        # 提取 ```json ... ``` 块
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None


def _clean_mermaid(text: str) -> str:
    """清理LLM输出的Mermaid文本"""
    text = text.strip()
    if "```mermaid" in text:
        text = text.split("```mermaid")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return text


@celery_app.task(name="app.tasks.note_tasks.recover_stuck_notes")
def recover_stuck_notes():
    """Celery Beat: 每30分钟扫描卡住超过30分钟的processing笔记并重新入队。"""
    _run(_recover_stuck_async())


async def _recover_stuck_async():
    from sqlalchemy import select, and_
    from app.core.database import AsyncSessionLocal
    from app.models.note import Note
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Note.id, Note.user_id).where(
                and_(Note.status == "processing", Note.created_at < cutoff)
            )
        )
        stuck = result.all()

    if not stuck:
        logger.info("recover_stuck_notes: no stuck notes")
        return

    logger.warning(f"recover_stuck_notes: re-queuing {len(stuck)} stuck note(s)")
    for note_id, user_id in stuck:
        process_note.delay(str(note_id), str(user_id))
        logger.info(f"  re-queued note {note_id}")


@celery_app.task
def generate_daily_tasks_all_users():
    """每日任务生成（Celery Beat调度）"""
    _run(_generate_daily_tasks_async())


async def _generate_daily_tasks_async():
    from app.core.database import AsyncSessionLocal
    from app.models.flashcard import Flashcard
    from sqlalchemy import select
    from datetime import date

    today = date.today()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Flashcard.user_id).where(Flashcard.due_date <= today).distinct()
        )
        user_ids = result.scalars().all()
        logger.info(f"Daily tasks: {len(user_ids)} users have due flashcards today")
