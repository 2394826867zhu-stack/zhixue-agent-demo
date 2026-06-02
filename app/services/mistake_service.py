import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.training import TrainingQuestion
from app.models.knowledge_point import KnowledgePoint
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError, LLMError

logger = logging.getLogger(__name__)

WRONG_SCORE_THRESHOLD = 60


class MistakeService:

    async def list_mistakes(
        self,
        db: AsyncSession,
        user_id: str,
        subject: str | None,
        knowledge_point_id: str | None,
        page: int,
        page_size: int,
        project_id: str | None = None,
    ) -> dict:
        uid = uuid.UUID(user_id)
        conditions = [
            TrainingQuestion.user_id == uid,
            TrainingQuestion.is_wrong == True,
            TrainingQuestion.is_retry == False,
        ]

        if knowledge_point_id:
            conditions.append(TrainingQuestion.knowledge_point_id == uuid.UUID(knowledge_point_id))

        if project_id:
            conditions.append(TrainingQuestion.project_id == uuid.UUID(project_id))

        if subject:
            conditions.append(
                TrainingQuestion.knowledge_point_id.in_(
                    select(KnowledgePoint.id).where(
                        KnowledgePoint.user_id == uid,
                        KnowledgePoint.subject == subject,
                    )
                )
            )

        query = (
            select(TrainingQuestion)
            .where(and_(*conditions))
            .order_by(TrainingQuestion.answered_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        questions = result.scalars().all()

        count_result = await db.execute(select(func.count()).where(and_(*conditions)))
        total = count_result.scalar() or 0

        return {"items": questions, "total": total, "page": page, "page_size": page_size}

    async def get_stats(self, db: AsyncSession, user_id: str) -> dict:
        uid = uuid.UUID(user_id)
        base_cond = [
            TrainingQuestion.user_id == uid,
            TrainingQuestion.is_wrong == True,
            TrainingQuestion.is_retry == False,
        ]

        total_result = await db.execute(select(func.count()).where(and_(*base_cond)))
        total = total_result.scalar() or 0

        # count by subject via join with knowledge_points
        subject_rows = await db.execute(
            select(KnowledgePoint.subject, func.count(TrainingQuestion.id))
            .join(TrainingQuestion, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
            .where(and_(*base_cond, KnowledgePoint.subject.isnot(None)))
            .group_by(KnowledgePoint.subject)
        )
        by_subject = {row[0]: row[1] for row in subject_rows}

        # top 5 knowledge points with most mistakes
        top_kp_rows = await db.execute(
            select(KnowledgePoint.id, KnowledgePoint.name, func.count(TrainingQuestion.id).label("cnt"))
            .join(TrainingQuestion, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
            .where(and_(*base_cond))
            .group_by(KnowledgePoint.id, KnowledgePoint.name)
            .order_by(func.count(TrainingQuestion.id).desc())
            .limit(5)
        )
        top_kps = [
            {"kp_id": str(row[0]), "kp_name": row[1], "count": row[2]}
            for row in top_kp_rows
        ]

        return {"total": total, "by_subject": by_subject, "top_kps": top_kps}

    async def create_retry(self, db: AsyncSession, question_id: str, user_id: str) -> TrainingQuestion:
        original = await self._get_mistake(db, question_id, user_id)
        uid = uuid.UUID(user_id)

        kp_result = await db.execute(
            select(KnowledgePoint).where(
                KnowledgePoint.id == original.knowledge_point_id,
                KnowledgePoint.user_id == uid,
            )
        )
        kp = kp_result.scalar_one_or_none()
        if not kp:
            raise NotFoundError("知识点")

        # check no unanswered retry already exists
        existing_retry = await db.execute(
            select(TrainingQuestion).where(
                TrainingQuestion.original_question_id == original.id,
                TrainingQuestion.user_answer == None,
            )
        )
        if existing_retry.scalar_one_or_none():
            raise ValidationError("该错题已有待作答的重练题，请先完成")

        from app.llm.client import llm_client
        from app.llm.prompts.training_prompts import TWIN_QUESTION_PROMPT, SYSTEM_TRAINING

        # v0.34 P1-5 · 错题孪生题（不是改数字，是换情境）
        try:
            raw = await llm_client.generate(
                TWIN_QUESTION_PROMPT.format(
                    original_question=original.question_text,
                    reference_answer=original.reference_answer or "无",
                    user_answer=original.user_answer or "未作答",
                    error_reason=original.error_reason or "未归类",
                ),
                system=SYSTEM_TRAINING,
                user_id=user_id,
                endpoint="mistake.create_retry_twin",
            )
        except Exception as e:
            logger.warning(f"Retry twin question generation failed: {e}")
            raise LLMError() from e
        items = _parse_json_safe(raw)
        if not items:
            raise ValidationError("题目生成失败，请稍后重试")

        item = items[0] if isinstance(items, list) else items
        retry_q = TrainingQuestion(
            session_id=None,
            user_id=uuid.UUID(user_id),
            knowledge_point_id=kp.id,
            bloom_level=kp.bloom_level,
            question_type=item.get("question_type", original.question_type),
            question_text=item.get("question_text", ""),
            reference_answer=item.get("reference_answer", ""),
            is_retry=True,
            original_question_id=original.id,
        )
        db.add(retry_q)
        await db.commit()
        await db.refresh(retry_q)
        return retry_q

    async def submit_retry_answer(
        self, db: AsyncSession, question_id: str, retry_question_id: str, user_id: str, user_answer: str
    ) -> dict:
        original = await self._get_mistake(db, question_id, user_id)

        retry_result = await db.execute(
            select(TrainingQuestion).where(
                TrainingQuestion.id == uuid.UUID(retry_question_id),
                TrainingQuestion.original_question_id == original.id,
                TrainingQuestion.is_retry == True,
            )
        )
        retry_q = retry_result.scalar_one_or_none()
        if not retry_q:
            raise NotFoundError("重练题目")
        if retry_q.user_answer is not None:
            raise ValidationError("该重练题已作答")

        from app.services.training_service import TrainingService
        score, feedback, is_wrong = await TrainingService()._grade_answer(retry_q, user_answer)

        retry_q.user_answer = user_answer
        retry_q.ai_score = score
        retry_q.ai_feedback = feedback
        retry_q.is_wrong = is_wrong
        retry_q.answered_at = datetime.now(timezone.utc)

        mistake_resolved = not is_wrong
        if mistake_resolved:
            original.is_wrong = False

        await db.commit()

        return {
            "retry_question_id": retry_q.id,
            "ai_score": score,
            "ai_feedback": feedback,
            "reference_answer": retry_q.reference_answer,
            "mistake_resolved": mistake_resolved,
        }

    async def remove_mistake(self, db: AsyncSession, question_id: str, user_id: str) -> None:
        question = await self._get_mistake(db, question_id, user_id)
        question.is_wrong = False
        await db.commit()

    async def _get_mistake(self, db: AsyncSession, question_id: str, user_id: str) -> TrainingQuestion:
        result = await db.execute(
            select(TrainingQuestion).where(TrainingQuestion.id == uuid.UUID(question_id))
        )
        q = result.scalar_one_or_none()
        if not q:
            raise NotFoundError("题目")
        if str(q.user_id) != user_id:
            raise PermissionDeniedError()
        if not q.is_wrong:
            raise ValidationError("该题目不在错题本中")
        return q


def _parse_json_safe(text: str) -> list:
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        result = json.loads(text)
        return result if isinstance(result, list) else [result]
    except Exception:
        return []


mistake_service = MistakeService()
