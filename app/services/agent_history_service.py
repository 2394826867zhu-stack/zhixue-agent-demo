"""Agent 浏览记录 + 对话搜索服务 — v2 PRD 9.7

行 669-673：控制台需要浏览记录入口 + 对话搜索
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.agent_history import AgentConversationLog
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class AgentHistoryService:

    async def list_logs(
        self, db: AsyncSession, user_id: str,
        page: int = 1, page_size: int = 20,
    ) -> dict:
        """浏览记录列表（按最近活跃倒序，PRD 9.7 行 669）。"""
        uid = uuid.UUID(user_id)
        total_q = await db.execute(
            select(func.count())
            .select_from(AgentConversationLog)
            .where(AgentConversationLog.user_id == uid)
        )
        total = total_q.scalar_one()

        result = await db.execute(
            select(AgentConversationLog)
            .where(AgentConversationLog.user_id == uid)
            .order_by(AgentConversationLog.last_activity_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def search(
        self, db: AsyncSession, user_id: str, query: str,
        page: int = 1, page_size: int = 20,
    ) -> dict:
        """对话搜索（PRD 9.7 行 673）。简单 ILIKE 起步。"""
        if not query or not query.strip():
            raise ValidationError("搜索关键词不能为空")
        uid = uuid.UUID(user_id)
        q = query.strip()
        like = f"%{q}%"

        base = select(AgentConversationLog).where(
            AgentConversationLog.user_id == uid,
            or_(
                AgentConversationLog.title.ilike(like),
                AgentConversationLog.last_message_preview.ilike(like),
                AgentConversationLog.search_blob.ilike(like),
            ),
        )

        total_q = await db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_q.scalar_one()

        result = await db.execute(
            base.order_by(AgentConversationLog.last_activity_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
        )
        return {"items": list(result.scalars().all()), "total": total, "query": q}

    async def upsert_log(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        title: str,
        last_message_preview: str | None = None,
        message_increment: int = 1,
        new_search_text: str = "",
        tool_called: str | None = None,
    ) -> AgentConversationLog:
        """供 agent_service 在每次对话推进时调用，幂等更新。"""
        result = await db.execute(
            select(AgentConversationLog).where(
                AgentConversationLog.user_id == user_id,
                AgentConversationLog.session_id == session_id,
            )
        )
        log = result.scalar_one_or_none()
        if log is None:
            log = AgentConversationLog(
                user_id=user_id,
                session_id=session_id,
                title=title[:255],
                last_message_preview=(last_message_preview or "")[:200] or None,
                message_count=message_increment,
                search_blob=new_search_text[:8000],
                tools_called={tool_called: 1} if tool_called else {},
            )
            db.add(log)
        else:
            log.title = log.title or title[:255]
            if last_message_preview:
                log.last_message_preview = last_message_preview[:200]
            log.message_count = (log.message_count or 0) + message_increment
            # 累加 search_blob，但限制总长度
            new_blob = (log.search_blob or "") + " " + new_search_text
            log.search_blob = new_blob[-8000:]
            if tool_called:
                tools = dict(log.tools_called or {})
                tools[tool_called] = tools.get(tool_called, 0) + 1
                log.tools_called = tools
            from datetime import datetime, timezone
            log.last_activity_at = datetime.now(timezone.utc)

        await db.flush()
        return log


agent_history_service = AgentHistoryService()
