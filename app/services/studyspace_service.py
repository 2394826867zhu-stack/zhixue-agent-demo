import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError, AppError
from app.models.curriculum import CurriculumChapter
from app.models.studyspace import StudySpaceSession
from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.schemas.studyspace import (
    StartSessionRequest, UpdateSessionRequest,
    StudySpaceSessionOut, CompleteSessionResponse, LessonProgress,
)
from app.schemas.curriculum import CurriculumLessonOut
from app.services.star_service import StarService


class StudySpaceService:
    async def start_session(
        self,
        db: AsyncSession,
        user_id: str,
        req: StartSessionRequest,
    ) -> StudySpaceSessionOut:
        # Verify chapter exists
        chapter = await db.get(CurriculumChapter, req.chapter_id)
        if not chapter:
            raise NotFoundError("课时不存在")

        # Check for existing active session on same chapter
        existing = await db.execute(
            select(StudySpaceSession).where(
                StudySpaceSession.user_id == uuid.UUID(user_id),
                StudySpaceSession.chapter_id == req.chapter_id,
                StudySpaceSession.status == "active",
            )
        )
        active = existing.scalar_one_or_none()
        if active:
            return await self._to_out(db, active, chapter)

        session = StudySpaceSession(
            user_id=uuid.UUID(user_id),
            chapter_id=req.chapter_id,
            status="active",
            progress=0,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return await self._to_out(db, session, chapter)

    async def get_session(
        self, db: AsyncSession, user_id: str, session_id: uuid.UUID
    ) -> StudySpaceSessionOut:
        session = await db.get(StudySpaceSession, session_id)
        if not session or str(session.user_id) != user_id:
            raise NotFoundError("会话不存在")
        chapter = await db.get(CurriculumChapter, session.chapter_id)
        return await self._to_out(db, session, chapter)

    async def update_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: uuid.UUID,
        req: UpdateSessionRequest,
    ) -> StudySpaceSessionOut:
        session = await db.get(StudySpaceSession, session_id)
        if not session or str(session.user_id) != user_id:
            raise NotFoundError("会话不存在")
        if session.status == "completed":
            raise AppError(400, "会话已完成", 400)

        if req.progress is not None:
            session.progress = max(0, min(100, req.progress))
        if req.agent_session_id is not None:
            session.agent_session_id = req.agent_session_id
        if req.status is not None and req.status in ("active", "paused"):
            session.status = req.status

        await db.commit()
        await db.refresh(session)
        chapter = await db.get(CurriculumChapter, session.chapter_id)
        return await self._to_out(db, session, chapter)

    async def complete_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: uuid.UUID,
    ) -> CompleteSessionResponse:
        session = await db.get(StudySpaceSession, session_id)
        if not session or str(session.user_id) != user_id:
            raise NotFoundError("会话不存在")
        if session.status == "completed":
            raise AppError(400, "会话已完成", 400)

        chapter = await db.get(CurriculumChapter, session.chapter_id)

        # Count KPs and flashcards created during this session (via agent session)
        kp_count = 0
        fc_count = 0
        if session.agent_session_id:
            kp_result = await db.execute(
                select(func.count()).select_from(KnowledgePoint).where(
                    KnowledgePoint.user_id == uuid.UUID(user_id),
                )
            )
            # simplified: count total KPs (accurate count would need session-level tagging)
            kp_count = session.kp_extracted
            fc_count = session.flashcards_created

        stars_earned = 30  # lesson_complete reward

        session.status = "completed"
        session.progress = 100
        session.completed_at = datetime.now(timezone.utc)
        session.stars_earned = stars_earned
        await db.commit()
        await db.refresh(session)

        # Award stars
        star_svc = StarService()
        await star_svc.award(
            db, user_id,
            amount=stars_earned,
            reason="lesson_complete",
            description=f"完成课时：{chapter.lesson_title}",
            meta={"session_id": str(session_id)},
        )

        # Find next lesson in same chapter or next chapter
        next_lesson = await self._find_next_lesson(db, chapter)

        return CompleteSessionResponse(
            session_id=session.id,
            kp_extracted=session.kp_extracted,
            flashcards_created=session.flashcards_created,
            stars_earned=stars_earned,
            next_lesson=CurriculumLessonOut.model_validate(next_lesson) if next_lesson else None,
        )

    async def list_sessions(
        self, db: AsyncSession, user_id: str, limit: int = 20
    ) -> list[StudySpaceSessionOut]:
        result = await db.execute(
            select(StudySpaceSession)
            .where(StudySpaceSession.user_id == uuid.UUID(user_id))
            .order_by(StudySpaceSession.created_at.desc())
            .limit(limit)
        )
        sessions = list(result.scalars().all())
        out = []
        for s in sessions:
            chapter = await db.get(CurriculumChapter, s.chapter_id)
            out.append(await self._to_out(db, s, chapter))
        return out

    async def get_curriculum_progress(
        self, db: AsyncSession, user_id: str, subject: str | None = None
    ) -> list[LessonProgress]:
        query = select(StudySpaceSession).where(
            StudySpaceSession.user_id == uuid.UUID(user_id)
        )
        result = await db.execute(query)
        sessions = list(result.scalars().all())

        # Build map: chapter_id -> best session
        chapter_map: dict[uuid.UUID, StudySpaceSession] = {}
        for s in sessions:
            if s.chapter_id not in chapter_map:
                chapter_map[s.chapter_id] = s
            else:
                existing = chapter_map[s.chapter_id]
                if s.status == "completed" or s.progress > existing.progress:
                    chapter_map[s.chapter_id] = s

        progress_list = []
        for chapter_id, s in chapter_map.items():
            status = s.status if s.status in ("completed",) else (
                "in_progress" if s.progress > 0 else "available"
            )
            progress_list.append(LessonProgress(
                chapter_id=chapter_id,
                status=status,
                progress_pct=s.progress,
                last_session_at=s.started_at,
            ))
        return progress_list

    async def _to_out(
        self, db: AsyncSession, session: StudySpaceSession, chapter: CurriculumChapter | None
    ) -> StudySpaceSessionOut:
        return StudySpaceSessionOut(
            id=session.id,
            chapter_id=session.chapter_id,
            chapter_title=chapter.chapter_title if chapter else "",
            lesson_title=chapter.lesson_title if chapter else "",
            subject=chapter.subject if chapter else "",
            status=session.status,
            progress=session.progress,
            agent_session_id=session.agent_session_id,
            kp_extracted=session.kp_extracted,
            flashcards_created=session.flashcards_created,
            stars_earned=session.stars_earned,
            started_at=session.started_at,
            completed_at=session.completed_at,
        )

    async def _find_next_lesson(
        self, db: AsyncSession, current: CurriculumChapter
    ) -> CurriculumChapter | None:
        # Try next lesson in same chapter
        result = await db.execute(
            select(CurriculumChapter).where(
                CurriculumChapter.subject == current.subject,
                CurriculumChapter.grade_type == current.grade_type,
                CurriculumChapter.grade_year == current.grade_year,
                CurriculumChapter.semester == current.semester,
                CurriculumChapter.chapter_index == current.chapter_index,
                CurriculumChapter.lesson_index == current.lesson_index + 1,
            )
        )
        nxt = result.scalar_one_or_none()
        if nxt:
            return nxt
        # Try first lesson of next chapter
        result = await db.execute(
            select(CurriculumChapter).where(
                CurriculumChapter.subject == current.subject,
                CurriculumChapter.grade_type == current.grade_type,
                CurriculumChapter.grade_year == current.grade_year,
                CurriculumChapter.semester == current.semester,
                CurriculumChapter.chapter_index == current.chapter_index + 1,
                CurriculumChapter.lesson_index == 1,
            )
        )
        return result.scalar_one_or_none()
