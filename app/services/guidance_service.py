import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.guidance import GuidanceSession, GuidanceMessage
from app.models.knowledge_point import KnowledgePoint
from app.core.exceptions import LLMError, NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 20  # keep last 20 turns for LLM context


class GuidanceService:

    async def start_session(
        self, db: AsyncSession, user_id: str, question: str, subject: str | None
    ) -> tuple[GuidanceSession, GuidanceMessage]:
        uid = uuid.UUID(user_id)
        title = question[:50] + ("..." if len(question) > 50 else "")

        session = GuidanceSession(
            user_id=uid,
            title=title,
            subject=subject,
        )
        db.add(session)
        await db.flush()

        # save user's opening question
        user_msg = GuidanceMessage(
            session_id=session.id,
            user_id=uid,
            role="user",
            content=question,
        )
        db.add(user_msg)
        await db.flush()

        # fetch related KPs for context
        kp_context = await self._fetch_kp_context(db, uid, subject, question)

        # AI first response
        ai_content = await self._call_llm(
            conversation=[{"role": "user", "content": question}],
            user_message=question,
            kp_context=kp_context,
        )

        ai_msg = GuidanceMessage(
            session_id=session.id,
            user_id=uid,
            role="assistant",
            content=ai_content,
        )
        db.add(ai_msg)
        session.message_count = 2

        await db.commit()
        await db.refresh(session)
        await db.refresh(ai_msg)
        return session, ai_msg

    async def chat(
        self, db: AsyncSession, session_id: str, user_id: str, message: str
    ) -> GuidanceMessage:
        uid = uuid.UUID(user_id)
        session = await self._get_session(db, session_id, user_id)
        if session.status == "resolved":
            raise ValidationError("该引导会话已结束，请开启新会话")

        # load recent conversation history
        history_result = await db.execute(
            select(GuidanceMessage)
            .where(GuidanceMessage.session_id == session.id)
            .order_by(GuidanceMessage.created_at.desc())
            .limit(MAX_CONTEXT_MESSAGES)
        )
        history = list(reversed(history_result.scalars().all()))
        conversation = [{"role": m.role, "content": m.content} for m in history]

        # save user message
        user_msg = GuidanceMessage(
            session_id=session.id,
            user_id=uid,
            role="user",
            content=message,
        )
        db.add(user_msg)
        await db.flush()

        kp_context = await self._fetch_kp_context(db, uid, session.subject, message)

        ai_content = await self._call_llm(
            conversation=conversation,
            user_message=message,
            kp_context=kp_context,
        )

        ai_msg = GuidanceMessage(
            session_id=session.id,
            user_id=uid,
            role="assistant",
            content=ai_content,
        )
        db.add(ai_msg)
        session.message_count += 2
        session.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(ai_msg)
        return ai_msg

    async def resolve_session(self, db: AsyncSession, session_id: str, user_id: str) -> GuidanceSession:
        session = await self._get_session(db, session_id, user_id)
        session.status = "resolved"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session

    async def list_sessions(
        self, db: AsyncSession, user_id: str, page: int, page_size: int
    ) -> dict:
        uid = uuid.UUID(user_id)
        query = (
            select(GuidanceSession)
            .where(GuidanceSession.user_id == uid)
            .order_by(GuidanceSession.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        sessions = result.scalars().all()

        count_result = await db.execute(
            select(func.count()).where(GuidanceSession.user_id == uid)
        )
        total = count_result.scalar() or 0
        return {"items": sessions, "total": total, "page": page, "page_size": page_size}

    async def get_session_detail(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> GuidanceSession:
        result = await db.execute(
            select(GuidanceSession)
            .options(selectinload(GuidanceSession.messages))
            .where(GuidanceSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("引导会话")
        if str(session.user_id) != user_id:
            raise PermissionDeniedError()
        return session

    async def _fetch_kp_context(
        self, db: AsyncSession, uid: uuid.UUID, subject: str | None, question: str
    ) -> str:
        """Fetch up to 5 relevant KPs (same subject, non-mastered) as context hint."""
        conditions = [KnowledgePoint.user_id == uid]
        if subject:
            conditions.append(KnowledgePoint.subject == subject)

        from sqlalchemy import and_
        result = await db.execute(
            select(KnowledgePoint.name, KnowledgePoint.content)
            .where(and_(*conditions))
            .order_by(KnowledgePoint.updated_at.desc())
            .limit(5)
        )
        rows = result.all()
        if not rows:
            return ""

        parts = []
        for name, content in rows:
            snippet = (content or "")[:80]
            parts.append(f"- {name}: {snippet}")
        return "\n".join(parts)

    async def _call_llm(
        self, conversation: list[dict], user_message: str, kp_context: str
    ) -> str:
        from app.llm.client import llm_client
        from app.llm.prompts.guidance_prompts import (
            SYSTEM_GUIDANCE,
            GUIDANCE_CONTEXT_PROMPT,
            GUIDANCE_NO_CONTEXT_PROMPT,
        )

        conv_text = "\n".join(
            f"{'学生' if m['role'] == 'user' else '老师'}：{m['content']}"
            for m in conversation[:-1]  # exclude the latest message (passed separately)
        )

        if kp_context:
            prompt = GUIDANCE_CONTEXT_PROMPT.format(
                kp_context=kp_context,
                conversation=conv_text or "（对话开始）",
                user_message=user_message,
            )
        else:
            prompt = GUIDANCE_NO_CONTEXT_PROMPT.format(
                conversation=conv_text or "（对话开始）",
                user_message=user_message,
            )

        try:
            return await llm_client.generate(prompt, system=SYSTEM_GUIDANCE)
        except Exception as e:
            logger.warning(f"Guidance LLM call failed: {e}")
            raise LLMError() from e

    async def _get_session(
        self, db: AsyncSession, session_id: str, user_id: str
    ) -> GuidanceSession:
        result = await db.execute(
            select(GuidanceSession).where(GuidanceSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("引导会话")
        if str(session.user_id) != user_id:
            raise PermissionDeniedError()
        return session


guidance_service = GuidanceService()
