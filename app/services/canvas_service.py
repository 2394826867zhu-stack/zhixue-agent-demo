"""StudySpace 画板服务 — v2 PRD 9.3 行 636"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.canvas import CanvasStroke
from app.models.studyspace import StudySpaceSession
from app.schemas.canvas import CanvasStrokeIn, CanvasStrokeBatch
from app.core.exceptions import NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)


class CanvasService:

    async def list_strokes(
        self, db: AsyncSession, session_id: str, user_id: str,
        page_index: int | None = None,
    ) -> list[CanvasStroke]:
        await self._assert_session(db, session_id, user_id)
        q = select(CanvasStroke).where(
            CanvasStroke.session_id == uuid.UUID(session_id),
        )
        if page_index is not None:
            q = q.where(CanvasStroke.page_index == page_index)
        q = q.order_by(CanvasStroke.page_index.asc(), CanvasStroke.sort_order.asc())
        result = await db.execute(q)
        return list(result.scalars().all())

    async def add_strokes(
        self, db: AsyncSession, session_id: str, user_id: str,
        batch: CanvasStrokeBatch,
    ) -> int:
        await self._assert_session(db, session_id, user_id)
        sid = uuid.UUID(session_id)
        uid = uuid.UUID(user_id)
        for s in batch.strokes:
            db.add(CanvasStroke(
                session_id=sid,
                user_id=uid,
                path_d=s.path_d,
                color=s.color,
                stroke_width=s.stroke_width,
                opacity=s.opacity,
                page_index=s.page_index,
                sort_order=s.sort_order,
                metadata_json=s.metadata_json,
            ))
        await db.commit()
        return len(batch.strokes)

    async def get_stroke(
        self, db: AsyncSession, stroke_id: str, user_id: str,
    ) -> CanvasStroke:
        """v0.32 · 单条详情"""
        result = await db.execute(
            select(CanvasStroke).where(CanvasStroke.id == uuid.UUID(stroke_id))
        )
        stroke = result.scalar_one_or_none()
        if stroke is None:
            raise NotFoundError("笔画不存在")
        if str(stroke.user_id) != user_id:
            raise PermissionDeniedError("无权查看此笔画")
        return stroke

    async def delete_stroke(
        self, db: AsyncSession, stroke_id: str, user_id: str,
    ) -> None:
        result = await db.execute(
            select(CanvasStroke).where(CanvasStroke.id == uuid.UUID(stroke_id))
        )
        stroke = result.scalar_one_or_none()
        if stroke is None:
            raise NotFoundError("笔画不存在")
        if str(stroke.user_id) != user_id:
            raise PermissionDeniedError("无权删除此笔画")
        await db.delete(stroke)
        await db.commit()

    async def clear_page(
        self, db: AsyncSession, session_id: str, user_id: str, page_index: int,
    ) -> int:
        await self._assert_session(db, session_id, user_id)
        result = await db.execute(
            delete(CanvasStroke).where(
                CanvasStroke.session_id == uuid.UUID(session_id),
                CanvasStroke.page_index == page_index,
            )
        )
        await db.commit()
        return result.rowcount or 0

    async def _assert_session(
        self, db: AsyncSession, session_id: str, user_id: str,
    ) -> None:
        result = await db.execute(
            select(StudySpaceSession).where(StudySpaceSession.id == uuid.UUID(session_id))
        )
        ss = result.scalar_one_or_none()
        if ss is None:
            raise NotFoundError("StudySpace 会话不存在")
        if str(ss.user_id) != user_id:
            raise PermissionDeniedError("无权访问此会话")


canvas_service = CanvasService()
