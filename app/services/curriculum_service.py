import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.curriculum import CurriculumChapter
from app.models.knowledge_point import KnowledgePoint
from app.models.note import Note
from app.schemas.knowledge_point import KnowledgePointResponse


class CurriculumService:
    async def list_chapters(
        self,
        db: AsyncSession,
        user_id: str,
        grade_type: str,
        grade_year: int,
        subject: str | None,
        semester: int | None,
    ) -> list[dict]:
        query = select(CurriculumChapter).where(
            CurriculumChapter.grade_type == grade_type,
            CurriculumChapter.grade_year == grade_year,
        )
        if subject:
            query = query.where(CurriculumChapter.subject == subject)
        if semester:
            query = query.where(CurriculumChapter.semester == semester)

        result = await db.execute(
            query.order_by(
                CurriculumChapter.subject.asc(),
                CurriculumChapter.semester.asc(),
                CurriculumChapter.chapter_index.asc(),
                CurriculumChapter.lesson_index.asc(),
            )
        )
        lessons = list(result.scalars().all())

        kp_counts = await self._kp_counts_by_chapter(db, uuid.UUID(user_id), [lesson.id for lesson in lessons])
        groups: dict[tuple[str, int, int, str], dict] = {}
        for lesson in lessons:
            key = (lesson.subject, lesson.semester, lesson.chapter_index, lesson.chapter_title)
            group = groups.setdefault(
                key,
                {
                    "chapter_index": lesson.chapter_index,
                    "chapter_title": lesson.chapter_title,
                    "subject": lesson.subject,
                    "semester": lesson.semester,
                    "lessons": [],
                },
            )
            group["lessons"].append({"chapter": lesson, "kp_count": kp_counts.get(lesson.id, 0)})

        return list(groups.values())

    async def get_chapter_kps(
        self,
        db: AsyncSession,
        chapter_id: str,
        user_id: str,
    ) -> list[KnowledgePointResponse]:
        chapter = await self._get_chapter(db, chapter_id)
        result = await db.execute(
            select(KnowledgePoint)
            .where(
                KnowledgePoint.chapter_id == chapter.id,
                KnowledgePoint.user_id == uuid.UUID(user_id),
            )
            .order_by(KnowledgePoint.updated_at.desc())
        )
        return [KnowledgePointResponse.model_validate(kp) for kp in result.scalars().all()]

    async def link_kp(
        self,
        db: AsyncSession,
        chapter_id: str,
        kp_id: str,
        user_id: str,
    ) -> KnowledgePointResponse:
        chapter = await self._get_chapter(db, chapter_id)
        result = await db.execute(select(KnowledgePoint).where(KnowledgePoint.id == uuid.UUID(kp_id)))
        kp = result.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")
        if str(kp.user_id) != user_id:
            raise PermissionDeniedError()

        kp.chapter_id = chapter.id
        await db.commit()
        await db.refresh(kp)
        return KnowledgePointResponse.model_validate(kp)

    async def generate_note_from_chapter(
        self,
        db: AsyncSession,
        chapter_id: str,
        user_id: str,
    ) -> dict:
        chapter = await self._get_chapter(db, chapter_id)
        source_input = (
            f"请围绕{chapter.grade_year}年级{chapter.subject}"
            f"《{chapter.chapter_title}》中的“{chapter.lesson_title}”整理学习笔记，"
            "输出适合学生复习的定义、公式、例题、易错点和知识框架。"
        )
        note = Note(
            user_id=uuid.UUID(user_id),
            title=f"{chapter.lesson_title}｜{chapter.chapter_title}",
            subject=chapter.subject,
            source_type="ai_generated",
            source_input=source_input,
            status="processing",
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        from app.tasks.note_tasks import process_note
        process_note.delay(str(note.id), user_id)

        return {"note_id": note.id, "status": note.status}

    async def _get_chapter(self, db: AsyncSession, chapter_id: str) -> CurriculumChapter:
        result = await db.execute(
            select(CurriculumChapter).where(CurriculumChapter.id == uuid.UUID(chapter_id))
        )
        chapter = result.scalar_one_or_none()
        if not chapter:
            raise NotFoundError("课程章节")
        return chapter

    async def _kp_counts_by_chapter(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        chapter_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, int]:
        if not chapter_ids:
            return {}
        rows = await db.execute(
            select(KnowledgePoint.chapter_id, func.count(KnowledgePoint.id))
            .where(
                KnowledgePoint.user_id == user_id,
                KnowledgePoint.chapter_id.in_(chapter_ids),
            )
            .group_by(KnowledgePoint.chapter_id)
        )
        return {row[0]: row[1] for row in rows if row[0] is not None}


curriculum_service = CurriculumService()

