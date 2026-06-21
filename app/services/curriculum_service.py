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

    async def get_chapter_detail(
        self,
        db: AsyncSession,
        chapter_id: str,
        user_id: str,
    ) -> dict:
        """章节（课时）详情 — 字段对齐前端 ChapterDetail。

        - title = lesson_title（这一行就是一个课时）
        - description = chapter_title（所属章节标题，作为详情描述）
        - kp_count = 该用户在此课时下的 KP 数
        - has_note = 该用户在此课时下是否已有「挂了笔记」的 KP（note_id 非空）
        - lessons = 同章节兄弟课时（各带该用户 kp_count）
        """
        uid = uuid.UUID(user_id)
        chapter = await self._get_chapter(db, chapter_id)

        # 同章节兄弟课时（含自身），按 lesson_index 排序
        sibling_rows = await db.execute(
            select(CurriculumChapter)
            .where(
                CurriculumChapter.subject == chapter.subject,
                CurriculumChapter.grade_type == chapter.grade_type,
                CurriculumChapter.grade_year == chapter.grade_year,
                CurriculumChapter.semester == chapter.semester,
                CurriculumChapter.chapter_index == chapter.chapter_index,
            )
            .order_by(CurriculumChapter.lesson_index.asc())
        )
        siblings = list(sibling_rows.scalars().all())

        kp_counts = await self._kp_counts_by_chapter(db, uid, [s.id for s in siblings])

        # has_note：此课时下是否有挂了 note 的 KP
        note_exists = await db.execute(
            select(func.count(KnowledgePoint.id)).where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.chapter_id == chapter.id,
                KnowledgePoint.note_id.is_not(None),
            )
        )
        has_note = (note_exists.scalar() or 0) > 0

        return {
            "id": chapter.id,
            "title": chapter.lesson_title,
            "subject": chapter.subject,
            "kp_count": kp_counts.get(chapter.id, 0),
            "has_note": has_note,
            "description": chapter.chapter_title,
            "lessons": [
                {"id": s.id, "title": s.lesson_title, "kp_count": kp_counts.get(s.id, 0)}
                for s in siblings
            ],
        }

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

