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

# v0.34 P1-1 · PRD 行 396 苏格拉底 5 轮上限
MAX_GUIDANCE_TURNS = 5  # 最多 5 轮（user 5 轮 + assistant 5 轮 = 10 条 message_count）
# 第 6 轮：自动给"提示词卡片"（关键 hint 但非完整答案）


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

        # v0.34 P1-1 · 苏格拉底 5 轮上限（user 已发条数）
        # message_count 包含 user+ai；user 单边发条数 = message_count // 2
        # 当前正在处理的 user_msg 已 add 但 message_count 还没 +2，user 已发条数 = (message_count // 2) + 1
        user_turns_after = (session.message_count // 2) + 1
        force_hint_card = user_turns_after > MAX_GUIDANCE_TURNS

        if force_hint_card:
            ai_content = await self._call_llm_hint_card(
                conversation=conversation,
                user_message=message,
                kp_context=kp_context,
            )
        else:
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

    async def _call_llm_hint_card(
        self, conversation: list[dict], user_message: str, kp_context: str
    ) -> str:
        """v0.34 P1-1 · 5 轮后 给"提示词卡片"

        不是完整答案，是"关键 hint + 解题思路骨架"，让学生能继续推但不放弃。
        典型结构：
        - 你已经摸到核心了
        - 关键点是 X
        - 套路：[1] 先做 A [2] 再算 B [3] 最后看 C
        - 你试试，做完发给我
        """
        from app.llm.client import llm_client

        hint_system = (
            "你是知曜的引导老师，学生已经在这道题上引导了 5 轮还没自己推出答案。"
            "现在你必须给一张【提示词卡片】，不能给完整答案，但要把解题骨架交给学生。"
            "结构：[1] 一句话肯定他的进展 [2] 指出关键转折点 [3] 给 3 步以内的骨架（每步只点关键变量/公式名，不算出结果）"
            "[4] 鼓励他自己做完发给你检查。"
            "全程不超过 150 字，voice 短句、不打鸡血、不'首先其次'。"
        )

        conv_text = "\n".join(
            f"{'学生' if m['role'] == 'user' else '老师'}：{m['content']}"
            for m in conversation[:-1]
        )
        prompt = (
            f"已用知识点：\n{kp_context or '无'}\n\n"
            f"对话历史：\n{conv_text}\n\n"
            f"学生最新消息：{user_message}\n\n"
            "请按上述结构产出【提示词卡片】。"
        )
        try:
            content = await llm_client.generate(prompt, system=hint_system)
            return content
        except Exception as e:
            logger.warning(f"Guidance hint card LLM failed: {e}")
            return "你已经摸到核心。这步是关键转折，自己试着推一下，做完发给我。"

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
