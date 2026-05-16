import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.schemas.knowledge_point import KnowledgePointCreate, KnowledgePointUpdate
from app.core.exceptions import NotFoundError, PermissionDeniedError


class KnowledgePointService:

    async def create(self, db: AsyncSession, user_id: str, data: KnowledgePointCreate) -> KnowledgePoint:
        kp = KnowledgePoint(
            user_id=uuid.UUID(user_id),
            name=data.name,
            subject=data.subject,
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
            fc_count = await self._flashcard_count(db, kp.id)
            items.append({"kp": kp, "flashcard_count": fc_count})

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_kp(self, db: AsyncSession, kp_id: str, user_id: str) -> tuple[KnowledgePoint, int]:
        kp = await self._get_kp(db, kp_id, user_id)
        fc_count = await self._flashcard_count(db, kp.id)
        return kp, fc_count

    async def update(self, db: AsyncSession, kp_id: str, user_id: str, data: KnowledgePointUpdate) -> KnowledgePoint:
        kp = await self._get_kp(db, kp_id, user_id)
        update_data = data.model_dump(exclude_none=True)
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

    async def _flashcard_count(self, db: AsyncSession, kp_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.count()).where(Flashcard.knowledge_point_id == kp_id)
        )
        return result.scalar() or 0


kp_service = KnowledgePointService()
