import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.training import TrainingSession, TrainingQuestion
from app.models.knowledge_point import KnowledgePoint
from app.schemas.training import TrainingStartRequest, AnswerRequest
from app.core.exceptions import LLMError, NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)

BLOOM_TO_QTYPE = {
    "remember": "fill_blank",
    "understand": "fill_blank",
    "apply": "calculation",
    "analyze": "calculation",
    "evaluate": "essay",
    "create": "essay",
}

# Wrong threshold
WRONG_SCORE_THRESHOLD = 60


class TrainingService:

    async def start_session(self, db: AsyncSession, user_id: str, data: TrainingStartRequest) -> TrainingSession:
        uid = uuid.UUID(user_id)

        kps = await self._select_kps(db, uid, data)
        if not kps:
            raise ValidationError("没有可用的知识点，请先生成笔记或创建知识点")

        session = TrainingSession(
            user_id=uid,
            mode=data.mode,
            subject=data.subject,
            knowledge_point_id=uuid.UUID(data.knowledge_point_id) if data.knowledge_point_id else None,
        )
        db.add(session)
        await db.flush()

        questions = await self._generate_questions(db, session, kps, data)
        if not questions:
            await db.rollback()
            raise LLMError()

        session.question_count = len(questions)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session(self, db: AsyncSession, session_id: str, user_id: str) -> TrainingSession:
        session = await self._get_session(db, session_id, user_id)
        return session

    async def list_sessions(self, db: AsyncSession, user_id: str, page: int, page_size: int) -> dict:
        uid = uuid.UUID(user_id)
        query = (
            select(TrainingSession)
            .where(TrainingSession.user_id == uid)
            .order_by(TrainingSession.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        sessions = result.scalars().all()

        count_result = await db.execute(
            select(func.count()).where(TrainingSession.user_id == uid)
        )
        total = count_result.scalar() or 0
        return {"items": sessions, "total": total, "page": page, "page_size": page_size}

    async def submit_answer(
        self, db: AsyncSession, session_id: str, question_id: str, user_id: str, data: AnswerRequest
    ) -> dict:
        session = await self._get_session(db, session_id, user_id)
        if session.status == "completed":
            raise ValidationError("该训练已结束")

        q_result = await db.execute(
            select(TrainingQuestion).where(
                TrainingQuestion.id == uuid.UUID(question_id),
                TrainingQuestion.session_id == session.id,
            )
        )
        question = q_result.scalar_one_or_none()
        if not question:
            raise NotFoundError("题目")
        if question.user_answer is not None:
            raise ValidationError("该题已作答")

        score, feedback, is_wrong = await self._grade_answer(question, data.user_answer)

        question.user_answer = data.user_answer
        question.ai_score = score
        question.ai_feedback = feedback
        question.is_wrong = is_wrong
        question.answered_at = datetime.now(timezone.utc)

        session.answered_count += 1

        session_completed = session.answered_count >= session.question_count
        if session_completed:
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            scores_result = await db.execute(
                select(TrainingQuestion.ai_score).where(
                    TrainingQuestion.session_id == session.id,
                    TrainingQuestion.ai_score.isnot(None),
                )
            )
            all_scores = [r for r in scores_result.scalars().all()]
            if all_scores:
                session.avg_score = round(sum(all_scores) / len(all_scores), 1)

        await db.commit()

        return {
            "question_id": question.id,
            "ai_score": score,
            "ai_feedback": feedback,
            "is_wrong": is_wrong,
            "reference": question.reference_answer,
            "session_completed": session_completed,
            "session_avg_score": session.avg_score,
        }

    async def _select_kps(self, db: AsyncSession, uid: uuid.UUID, data: TrainingStartRequest) -> list[KnowledgePoint]:
        if data.mode == "single_kp":
            if not data.knowledge_point_id:
                raise ValidationError("single_kp 模式需要提供 knowledge_point_id")
            result = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.id == uuid.UUID(data.knowledge_point_id),
                    KnowledgePoint.user_id == uid,
                )
            )
            kp = result.scalar_one_or_none()
            if not kp:
                raise NotFoundError("知识点")
            return [kp]
        else:
            # subject mode: prioritize new/overdue (mastery_status != 'mastered')
            conditions = [KnowledgePoint.user_id == uid]
            if data.subject:
                conditions.append(KnowledgePoint.subject == data.subject)

            # first fetch non-mastered, then fill with mastered if needed
            result = await db.execute(
                select(KnowledgePoint)
                .where(and_(*conditions, KnowledgePoint.mastery_status != "mastered"))
                .order_by(KnowledgePoint.updated_at.asc())
                .limit(data.question_count)
            )
            kps = list(result.scalars().all())

            if len(kps) < data.question_count:
                remaining = data.question_count - len(kps)
                existing_ids = [kp.id for kp in kps]
                extra_result = await db.execute(
                    select(KnowledgePoint)
                    .where(and_(*conditions, KnowledgePoint.id.notin_(existing_ids)))
                    .limit(remaining)
                )
                kps.extend(extra_result.scalars().all())

            return kps

    async def _generate_questions(
        self, db: AsyncSession, session: TrainingSession, kps: list[KnowledgePoint], data: TrainingStartRequest
    ) -> list[TrainingQuestion]:
        from app.llm.client import llm_client
        from app.llm.prompts.training_prompts import QUESTION_GENERATE_PROMPT, SYSTEM_TRAINING

        questions = []

        if data.mode == "single_kp":
            count_per_kp = data.question_count
        else:
            # distribute questions across KPs evenly
            count_per_kp = max(1, data.question_count // len(kps))

        for kp in kps:
            try:
                raw = await llm_client.generate(
                    QUESTION_GENERATE_PROMPT.format(
                        name=kp.name,
                        content=kp.content or "（无详细内容）",
                        key_formula=kp.key_formula or "无",
                        bloom_level=kp.bloom_level,
                        count=count_per_kp,
                    ),
                    system=SYSTEM_TRAINING,
                )
                cards_data = _parse_json_safe(raw)
                for item in cards_data:
                    q = TrainingQuestion(
                        session_id=session.id,
                        user_id=session.user_id,
                        knowledge_point_id=kp.id,
                        bloom_level=kp.bloom_level,
                        question_type=item.get("question_type", BLOOM_TO_QTYPE.get(kp.bloom_level, "fill_blank")),
                        question_text=item.get("question_text", ""),
                        reference_answer=item.get("reference_answer", ""),
                    )
                    db.add(q)
                    questions.append(q)
            except Exception as e:
                logger.warning(f"Failed to generate questions for KP {kp.id}: {e}")

        return questions

    async def _grade_answer(self, question: TrainingQuestion, user_answer: str) -> tuple[int, str, bool]:
        from app.llm.client import llm_client
        from app.llm.prompts.training_prompts import ANSWER_GRADE_PROMPT, SYSTEM_TRAINING

        try:
            raw = await llm_client.generate(
                ANSWER_GRADE_PROMPT.format(
                    question_text=question.question_text,
                    reference_answer=question.reference_answer,
                    user_answer=user_answer,
                    question_type=question.question_type,
                    bloom_level=question.bloom_level,
                ),
                system=SYSTEM_TRAINING,
            )
            data = _parse_json_safe(raw)
            if isinstance(data, list):
                data = data[0] if data else {}
            score = int(data.get("score", 50))
            score = max(0, min(100, score))
            feedback = str(data.get("feedback", "评分完成"))
            is_wrong = bool(data.get("is_wrong", score < WRONG_SCORE_THRESHOLD))
            return score, feedback, is_wrong
        except Exception as e:
            logger.warning(f"Grading failed for question {question.id}: {e}")
            raise LLMError() from e

    async def _get_session(self, db: AsyncSession, session_id: str, user_id: str) -> TrainingSession:
        result = await db.execute(
            select(TrainingSession).where(TrainingSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("训练会话")
        if str(session.user_id) != user_id:
            raise PermissionDeniedError()
        return session


def _parse_json_safe(text: str) -> list | dict:
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        return []


training_service = TrainingService()
