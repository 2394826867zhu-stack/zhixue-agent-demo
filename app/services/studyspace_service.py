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

        uid = uuid.UUID(user_id)

        # v0.27 Bug-02 · 强制单 active SS session（PRD 9.3 行 638 中途退出保留进度）
        # 如果同一 chapter 已有 active session，直接复用
        existing = await db.execute(
            select(StudySpaceSession).where(
                StudySpaceSession.user_id == uid,
                StudySpaceSession.chapter_id == req.chapter_id,
                StudySpaceSession.status == "active",
            )
        )
        active = existing.scalar_one_or_none()
        if active:
            return await self._to_out(db, active, chapter)

        # 其他 chapter 的 active session → 自动 paused（保证 find_active_ss_session_id 返回唯一）
        from sqlalchemy import update as _sql_update
        await db.execute(
            _sql_update(StudySpaceSession)
            .where(
                StudySpaceSession.user_id == uid,
                StudySpaceSession.status == "active",
            )
            .values(status="paused")
        )

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

        # v0.27 Q-04 · Agent 切换 celebrate 状态（PRD 2.1 行 167）
        try:
            from app.services.agent_state_service import agent_state_service
            await agent_state_service.set_celebrate(
                db, user_id, reason=f"完成「{lesson_label}」",
            )
        except Exception:
            pass

        # v0.27 Q-09 · 自动批量生成闪卡（PRD 行 553 强反馈）
        # 找出该用户在本 SS 期间没闪卡的 KP，每个生成 1 张
        fc_auto_created = 0
        try:
            from app.services.fsrs_service import fsrs_service
            from app.models.flashcard import Flashcard
            kp_rows = await db.execute(
                select(KnowledgePoint)
                .outerjoin(Flashcard, Flashcard.knowledge_point_id == KnowledgePoint.id)
                .where(
                    KnowledgePoint.user_id == uuid.UUID(user_id),
                    Flashcard.id.is_(None),
                )
                .limit(20)
            )
            for kp in kp_rows.scalars().all():
                if not (kp.name and kp.content):
                    continue
                try:
                    await fsrs_service.create_card(
                        db, user_id,
                        knowledge_point_id=str(kp.id),
                        front=kp.name,
                        back=(kp.content or "")[:500],
                        card_type="concept",
                    )
                    fc_auto_created += 1
                except Exception:
                    continue
            if fc_auto_created:
                session.flashcards_created = session.flashcards_created + fc_auto_created
                await db.commit()
        except Exception as _e:
            logger.warning(f"Auto flashcard generation skipped: {_e}")

        # v0.25 + v0.27 Q-08 · StudySpace 时间线写多条节点（PRD 行 438）
        try:
            from app.services.ss_timeline_service import ss_timeline_service
            # 节点 1：课程总结
            await ss_timeline_service.append_system_node(
                db,
                session_id=session_id,
                user_id=uuid.UUID(user_id),
                kind="agent_action",
                title="课程完成",
                content=f"完成「{lesson_label}」· 知星 +{stars_earned}",
                payload={
                    "tool": "complete_session",
                    "lesson": lesson_label,
                    "stars_earned": stars_earned,
                },
            )
            # 节点 2：KP 提取（如有）
            if kp_count > 0:
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=session_id,
                    user_id=uuid.UUID(user_id),
                    kind="kp_extracted",
                    title=f"提炼 {kp_count} 个知识点",
                    payload={"count": kp_count, "lesson": lesson_label},
                )
            # 节点 3：闪卡生成（含本次自动批量）
            total_fc = fc_count + fc_auto_created
            if total_fc > 0:
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=session_id,
                    user_id=uuid.UUID(user_id),
                    kind="agent_action",
                    title=f"生成 {total_fc} 张闪卡",
                    payload={
                        "auto": fc_auto_created,
                        "existing": fc_count,
                        "total": total_fc,
                    },
                )
            await db.commit()
        except Exception:
            # 时间线写入失败不阻断完成流程
            pass

        # v0.29 Memory · SS 完成 → 写 episode
        try:
            from app.services.episodic_memory_service import record_event
            summary = f"完成课时「{lesson_label}」"
            if kp_count or total_fc:
                summary += f"，提取 {kp_count} 个知识点，生成 {total_fc} 张闪卡"
            summary += "。"
            await record_event(
                db, user_id=uuid.UUID(user_id),
                event_kind="ss_completed",
                summary=summary,
                detail={
                    "lesson": lesson_label,
                    "session_id": str(session_id),
                    "subject": chapter.subject if chapter else None,
                    "kp_extracted": kp_count,
                    "flashcards_created": total_fc,
                },
                ref_project_id=session.project_id,
                emotional_tone="positive",
                session_id=session.agent_session_id,
            )
        except Exception as _e:
            logger.warning(f"ss_completed episode hook failed: {_e}")

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
