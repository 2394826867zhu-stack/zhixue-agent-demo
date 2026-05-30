"""死信队列服务（F-11）：记录/查询/标记已处理 Celery 失败任务。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter import DeadLetterTask


class DeadLetterService:
    async def record_failure(
        self,
        db: AsyncSession,
        task_name: str,
        task_id: str | None = None,
        args: list | None = None,
        kwargs: dict | None = None,
        error: str = "",
        traceback: str | None = None,
        retries: int = 0,
    ) -> DeadLetterTask:
        entry = DeadLetterTask(
            task_name=task_name,
            task_id=task_id,
            payload={"args": list(args or []), "kwargs": dict(kwargs or {})},
            error=(error or "")[:5000],
            traceback=traceback[:20000] if traceback else None,
            retries=retries,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    async def list_failures(
        self, db: AsyncSession, limit: int = 50, resolved: bool | None = None
    ) -> list[DeadLetterTask]:
        q = (
            select(DeadLetterTask)
            .order_by(DeadLetterTask.created_at.desc())
            .limit(limit)
        )
        if resolved is not None:
            q = q.where(DeadLetterTask.resolved == resolved)
        return list((await db.execute(q)).scalars().all())

    async def mark_resolved(
        self, db: AsyncSession, entry_id: str
    ) -> DeadLetterTask | None:
        try:
            eid = uuid.UUID(entry_id)
        except (ValueError, TypeError):
            return None
        entry = (
            await db.execute(
                select(DeadLetterTask).where(DeadLetterTask.id == eid)
            )
        ).scalar_one_or_none()
        if entry:
            entry.resolved = True
            await db.commit()
        return entry


dead_letter_service = DeadLetterService()
