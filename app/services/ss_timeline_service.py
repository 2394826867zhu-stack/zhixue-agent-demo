"""StudySpace 时间线服务 — v2 PRD 行 436-448"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.studyspace_timeline import StudySpaceTimelineNode
from app.models.studyspace import StudySpaceSession
from app.schemas.studyspace_timeline import TimelineUserAddRequest, TimelineNodePatch
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


# PRD 行 444-448：哪些节点用户不能改
_NON_EDITABLE_KINDS = {
    "training_result", "mistake", "flashcard_result",
    "agent_action",  # Agent 关键调度结果（"判题事实"等同视为不可改）
}


async def find_active_ss_session_id(
    db: AsyncSession, user_id: uuid.UUID,
) -> uuid.UUID | None:
    """查找用户当前活动中的 StudySpace 会话 id（用于自动写时间线）。

    返回最近的 status='active' 会话。无 active 时返回 None。
    """
    from app.models.studyspace import StudySpaceSession
    result = await db.execute(
        select(StudySpaceSession)
        .where(
            StudySpaceSession.user_id == user_id,
            StudySpaceSession.status == "active",
        )
        .order_by(StudySpaceSession.started_at.desc())
        .limit(1)
    )
    ss = result.scalar_one_or_none()
    return ss.id if ss else None


class SSTimelineService:

    async def list_nodes(
        self, db: AsyncSession, session_id: str, user_id: str,
    ) -> list[StudySpaceTimelineNode]:
        await self._assert_session_access(db, session_id, user_id)
        result = await db.execute(
            select(StudySpaceTimelineNode)
            .where(StudySpaceTimelineNode.session_id == uuid.UUID(session_id))
            .order_by(
                StudySpaceTimelineNode.sort_order.asc(),
                StudySpaceTimelineNode.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    async def user_add_node(
        self, db: AsyncSession, session_id: str, user_id: str,
        data: TimelineUserAddRequest,
    ) -> StudySpaceTimelineNode:
        """用户手动追加 content / reflection 节点。"""
        await self._assert_session_access(db, session_id, user_id)
        next_sort = await self._next_sort(db, session_id)
        node = StudySpaceTimelineNode(
            session_id=uuid.UUID(session_id),
            user_id=uuid.UUID(user_id),
            kind=data.kind,
            title=data.title,
            content=data.content,
            sort_order=next_sort,
            is_editable=True,  # user-authored content/reflection 均可编辑
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    async def patch_node(
        self, db: AsyncSession, node_id: str, user_id: str,
        data: TimelineNodePatch,
    ) -> StudySpaceTimelineNode:
        node = await self._fetch_node(db, node_id, user_id)
        if not node.is_editable:
            raise PermissionDeniedError("此节点为系统记录，不可改写（PRD 行 444）")
        if data.title is not None:
            node.title = data.title
        if data.content is not None:
            node.content = data.content
        await db.commit()
        await db.refresh(node)
        return node

    # ── 系统级写入（其他模块调用）─────────────────────────────────────

    async def append_system_node(
        self,
        db: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        kind: str,
        title: str | None = None,
        content: str | None = None,
        payload: dict | None = None,
        ref_kp_id: uuid.UUID | None = None,
        ref_flashcard_id: uuid.UUID | None = None,
        ref_training_question_id: uuid.UUID | None = None,
        ref_note_id: uuid.UUID | None = None,
    ) -> StudySpaceTimelineNode:
        """供 studyspace / training / flashcard / agent_tools 等内部调用。"""
        next_sort = await self._next_sort(db, str(session_id))
        is_editable = kind not in _NON_EDITABLE_KINDS
        node = StudySpaceTimelineNode(
            session_id=session_id,
            user_id=user_id,
            kind=kind,
            title=title,
            content=content,
            payload=payload or {},
            ref_kp_id=ref_kp_id,
            ref_flashcard_id=ref_flashcard_id,
            ref_training_question_id=ref_training_question_id,
            ref_note_id=ref_note_id,
            sort_order=next_sort,
            is_editable=is_editable,
        )
        db.add(node)
        await db.flush()
        return node

    # ── 内部 ──────────────────────────────────────────────────────────

    async def _next_sort(self, db: AsyncSession, session_id: str) -> int:
        result = await db.execute(
            select(func.coalesce(func.max(StudySpaceTimelineNode.sort_order), -1))
            .where(StudySpaceTimelineNode.session_id == uuid.UUID(session_id))
        )
        return (result.scalar() or -1) + 1

    async def _assert_session_access(
        self, db: AsyncSession, session_id: str, user_id: str,
    ) -> None:
        result = await db.execute(
            select(StudySpaceSession).where(StudySpaceSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("StudySpace 会话不存在")
        if str(session.user_id) != user_id:
            raise PermissionDeniedError("无权访问此会话")

    async def _fetch_node(
        self, db: AsyncSession, node_id: str, user_id: str,
    ) -> StudySpaceTimelineNode:
        try:
            nid = uuid.UUID(node_id)
            uid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            raise ValidationError("node_id 或 user_id 格式不合法")

        result = await db.execute(
            select(StudySpaceTimelineNode).where(StudySpaceTimelineNode.id == nid)
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise NotFoundError("时间线节点不存在")
        if node.user_id != uid:
            raise PermissionDeniedError("无权访问此节点")
        return node


ss_timeline_service = SSTimelineService()
