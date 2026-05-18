import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.models.curriculum import CurriculumChapter
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate
from app.core.exceptions import NotFoundError, PermissionDeniedError


class KnowledgePointService:

    async def create(self, db: AsyncSession, user_id: str, data: KnowledgePointCreate) -> KnowledgePoint:
        await self._ensure_chapter_exists(db, data.chapter_id)
        kp = KnowledgePoint(
            user_id=uuid.UUID(user_id),
            name=data.name,
            subject=data.subject,
            chapter_id=data.chapter_id,
            content=data.content,
            key_formula=data.key_formula,
            bloom_level=data.bloom_level,
            tags=data.tags,
        )
        db.add(kp)
        await db.commit()
        await db.refresh(kp)
        return kp

    async def list_kps(
        self,
        db: AsyncSession,
        user_id: str,
        subject: str | None,
        mastery_status: str | None,
        bloom_level: str | None,
        note_id: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        conditions = [KnowledgePoint.user_id == uuid.UUID(user_id)]
        if subject:
            conditions.append(KnowledgePoint.subject == subject)
        if mastery_status:
            conditions.append(KnowledgePoint.mastery_status == mastery_status)
        if bloom_level:
            conditions.append(KnowledgePoint.bloom_level == bloom_level)
        if note_id:
            conditions.append(KnowledgePoint.note_id == uuid.UUID(note_id))

        query = (
            select(KnowledgePoint)
            .where(and_(*conditions))
            .order_by(KnowledgePoint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        kps = result.scalars().all()

        count_result = await db.execute(
            select(func.count()).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        items = []
        for kp in kps:
            fc_count = await self._flashcard_count(db, uuid.UUID(user_id), kp.id)
            fc_info = await self._earliest_flashcard_info(db, uuid.UUID(user_id), kp.id)
            items.append({"kp": kp, "flashcard_count": fc_count, **fc_info})

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_kp(self, db: AsyncSession, kp_id: str, user_id: str) -> tuple[KnowledgePoint, int]:
        kp = await self._get_kp(db, kp_id, user_id)
        fc_count = await self._flashcard_count(db, uuid.UUID(user_id), kp.id)
        return kp, fc_count

    async def update(self, db: AsyncSession, kp_id: str, user_id: str, data: KnowledgePointUpdate) -> KnowledgePoint:
        kp = await self._get_kp(db, kp_id, user_id)
        update_data = data.model_dump(exclude_none=True)
        if "chapter_id" in update_data:
            await self._ensure_chapter_exists(db, update_data["chapter_id"])
        for field, value in update_data.items():
            setattr(kp, field, value)
        kp.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(kp)
        return kp

    async def delete(self, db: AsyncSession, kp_id: str, user_id: str) -> None:
        kp = await self._get_kp(db, kp_id, user_id)
        await db.delete(kp)
        await db.commit()

    async def get_stats(self, db: AsyncSession, user_id: str) -> dict:
        uid = uuid.UUID(user_id)

        rows = await db.execute(
            select(KnowledgePoint.mastery_status, func.count())
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.mastery_status)
        )
        status_counts = {row[0]: row[1] for row in rows}

        subject_rows = await db.execute(
            select(KnowledgePoint.subject, func.count())
            .where(KnowledgePoint.user_id == uid, KnowledgePoint.subject.isnot(None))
            .group_by(KnowledgePoint.subject)
        )
        by_subject = {row[0]: row[1] for row in subject_rows}

        total = sum(status_counts.values())
        return {
            "total": total,
            "new": status_counts.get("new", 0),
            "learning": status_counts.get("learning", 0),
            "reviewing": status_counts.get("reviewing", 0),
            "mastered": status_counts.get("mastered", 0),
            "by_subject": by_subject,
        }

    async def _get_kp(self, db: AsyncSession, kp_id: str, user_id: str) -> KnowledgePoint:
        result = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.id == uuid.UUID(kp_id))
        )
        kp = result.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")
        if str(kp.user_id) != user_id:
            raise PermissionDeniedError()
        return kp

    async def _ensure_chapter_exists(self, db: AsyncSession, chapter_id: uuid.UUID | None) -> None:
        if chapter_id is None:
            return
        result = await db.execute(
            select(CurriculumChapter.id).where(CurriculumChapter.id == chapter_id)
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError("课程章节")

    async def _flashcard_count(self, db: AsyncSession, user_id: uuid.UUID, kp_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == user_id,
                Flashcard.knowledge_point_id == kp_id,
            )
        )
        return result.scalar() or 0

    async def _earliest_flashcard_info(self, db: AsyncSession, user_id: uuid.UUID, kp_id: uuid.UUID) -> dict:
        result = await db.execute(
            select(Flashcard.due_date, Flashcard.stability)
            .where(
                Flashcard.user_id == user_id,
                Flashcard.knowledge_point_id == kp_id,
            )
            .order_by(Flashcard.due_date.asc())
            .limit(1)
        )
        row = result.one_or_none()
        if not row:
            return {"next_review_date": None, "stability": None}
        return {"next_review_date": str(row[0]), "stability": row[1]}


kp_service = KnowledgePointService()
