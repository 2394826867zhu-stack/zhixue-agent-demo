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
        lesson_label = chapter.lesson_title if chapter else "课时"
        star_svc = StarService()
        await star_svc.award(
            db, user_id,
            amount=stars_earned,
            reason="lesson_complete",
            description=f"完成课时：{lesson_label}",
            meta={"session_id": str(session_id)},
        )

        # Auto-complete matching system tasks
        from app.services.task_service import task_service as _task_svc
        await _task_svc.auto_complete_system_tasks(db, user_id, "lesson_complete")

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

        # Batch load chapters to avoid N+1
        chapter_ids = list({s.chapter_id for s in sessions if s.chapter_id is not None})
        chapters: dict[uuid.UUID, CurriculumChapter] = {}
        if chapter_ids:
            ch_result = await db.execute(
                select(CurriculumChapter).where(CurriculumChapter.id.in_(chapter_ids))
            )
            chapters = {c.id: c for c in ch_result.scalars().all()}

        return [
            await self._to_out(db, s, chapters.get(s.chapter_id))
            for s in sessions
        ]

    async def get_curriculum_progress(
        self, db: AsyncSession, user_id: str, subject: str | None = None
    ) -> list[LessonProgress]:
        from sqlalchemy import case
        uid = uuid.UUID(user_id)

        # Aggregate per chapter: best status rank (2=completed, 1=in_progress, 0=available)
        # and max progress. Single query replaces loading all sessions.
        subq = (
            select(
                StudySpaceSession.chapter_id,
                func.max(
                    case(
                        (StudySpaceSession.status == "completed", 2),
                        (StudySpaceSession.progress > 0, 1),
                        else_=0,
                    )
                ).label("best_status_rank"),
                func.max(StudySpaceSession.progress).label("best_progress"),
                func.max(StudySpaceSession.started_at).label("last_session_at"),
            )
            .where(
                StudySpaceSession.user_id == uid,
                StudySpaceSession.chapter_id.isnot(None),
            )
            .group_by(StudySpaceSession.chapter_id)
        ).subquery()

        result = await db.execute(select(subq))
        rows = result.all()

        progress_list = []
        for row in rows:
            rank = row.best_status_rank
            if rank >= 2:
                status = "completed"
            elif rank == 1:
                status = "in_progress"
            else:
                status = "available"
            progress_list.append(LessonProgress(
                chapter_id=row.chapter_id,
                status=status,
                progress_pct=row.best_progress,
                last_session_at=row.last_session_at,
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
