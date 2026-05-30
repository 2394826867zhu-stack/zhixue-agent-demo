import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.training import TrainingSession, TrainingQuestion
from app.models.knowledge_point import KnowledgePoint
from app.models.project import ProjectTreeNode
from app.schemas.training import (
    TrainingStartRequest, AnswerRequest, ComposeQuizRequest,
)
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

    # v0.26 · 组卷模式（PRD 9.4 行 645）─────────────────────────────────
    async def compose_quiz(
        self, db: AsyncSession, user_id: str, data: ComposeQuizRequest,
    ) -> TrainingSession:
        """组卷模式：选题型 / 题量 / 难度 / 范围 → 生成混合题型 TrainingSession。"""
        uid = uuid.UUID(user_id)

        # 1. 解析范围（按优先级）→ 知识点池
        kps = await self._resolve_compose_kp_pool(db, uid, data)
        if not kps:
            raise ValidationError("范围内没有可用的知识点")

        # 2. 按难度过滤
        kps = [k for k in kps if k.difficulty_tier in data.difficulty_tiers]
        if not kps:
            raise ValidationError(f"范围内没有匹配难度 {data.difficulty_tiers} 的知识点")

        # v0.34 P1-3 · 交错练习（PRD 行 367-369）
        # 学完 ≥3 节课后启用 → 30% 题目来自历史相关 KP
        interleave_ratio = 0.0
        try:
            from app.models.studyspace import StudySpaceSession
            from sqlalchemy import func
            ss_done = await db.execute(
                select(func.count()).select_from(StudySpaceSession).where(
                    StudySpaceSession.user_id == uid,
                    StudySpaceSession.status == "completed",
                )
            )
            n_completed_ss = ss_done.scalar_one() or 0
            if n_completed_ss >= 3:
                interleave_ratio = 0.3
        except Exception as _e:
            logger.debug(f"interleave check skipped: {_e}")

        interleave_kps: list[KnowledgePoint] = []
        if interleave_ratio > 0 and data.question_count >= 3:
            try:
                # 用 RAG 召回与当前 KP 池相关的"历史" KP（不在当前池）
                from app.services.rag_service import search as rag_search
                # 用第一个 KP 名做种子检索
                seed_kp = kps[0]
                query = f"{seed_kp.subject or ''} {seed_kp.name}"
                hits = await rag_search(
                    db, user_id=uid, query=query, top_k=15,
                    doc_kinds=["kp"], include_official=False,
                )
                current_pool_ids = {k.id for k in kps}
                ext_kp_ids = []
                for h in hits:
                    try:
                        h_id = uuid.UUID(h["doc_id"])
                    except Exception:
                        continue
                    if h_id not in current_pool_ids:
                        ext_kp_ids.append(h_id)
                    if len(ext_kp_ids) >= 5:
                        break
                if ext_kp_ids:
                    r = await db.execute(
                        select(KnowledgePoint).where(
                            KnowledgePoint.user_id == uid,
                            KnowledgePoint.id.in_(ext_kp_ids),
                            KnowledgePoint.difficulty_tier.in_(data.difficulty_tiers),
                        )
                    )
                    interleave_kps = list(r.scalars().all())
                    logger.info(f"interleave: pulled {len(interleave_kps)} historical KPs into quiz pool")
            except Exception as _e:
                logger.warning(f"interleave RAG call failed (skip): {_e}")

        # 3. 创建 session
        session = TrainingSession(
            user_id=uid,
            mode="compose",
            subject=data.subject,
            ss_session_id=data.ss_session_id,  # v0.27 Q-05 · 前端显式挂载
        )
        db.add(session)
        await db.flush()

        # 4. 按 question_count 在 KP 池上轮询出题，每题随机分配 question_types 中一种
        import random
        type_pool = list(data.question_types)
        from app.llm.client import llm_client
        from app.llm.prompts.training_prompts import QUESTION_GENERATE_PROMPT, SYSTEM_TRAINING

        questions: list[TrainingQuestion] = []
        # v0.34 P1-3 · 构造交错池：interleave_ratio 比例来自历史 KP
        n_interleave = int(round(data.question_count * interleave_ratio)) if interleave_kps else 0
        n_primary = data.question_count - n_interleave
        primary_cycle = (kps * ((n_primary // len(kps)) + 1))[:n_primary] if n_primary > 0 else []
        interleave_cycle = (
            (interleave_kps * ((n_interleave // len(interleave_kps)) + 1))[:n_interleave]
            if (n_interleave > 0 and interleave_kps) else []
        )
        # 打散：把交错题穿插进主题中（每 3 题塞 1 题历史）
        kp_cycle = []
        prim_iter = iter(primary_cycle)
        inter_iter = iter(interleave_cycle)
        primary_left, inter_left = len(primary_cycle), len(interleave_cycle)
        while primary_left or inter_left:
            for _ in range(2):
                if primary_left:
                    try:
                        kp_cycle.append(next(prim_iter))
                        primary_left -= 1
                    except StopIteration:
                        primary_left = 0
            if inter_left:
                try:
                    kp_cycle.append(next(inter_iter))
                    inter_left -= 1
                except StopIteration:
                    inter_left = 0
        for idx, kp in enumerate(kp_cycle):
            qtype = type_pool[idx % len(type_pool)]
            try:
                raw = await llm_client.generate(
                    QUESTION_GENERATE_PROMPT.format(
                        name=kp.name,
                        content=kp.content or "（无详细内容）",
                        key_formula=kp.key_formula or "无",
                        bloom_level=kp.bloom_level,
                        count=1,
                    ) + f"\n\n【强制题型】请生成一道 {qtype} 题。",
                    system=SYSTEM_TRAINING,
                    user_id=user_id,
                    endpoint="training.compose_quiz",
                )
                items = _parse_json_safe(raw)
                if not isinstance(items, list) or not items:
                    continue
                item = items[0]
                q = TrainingQuestion(
                    session_id=session.id,
                    user_id=uid,
                    knowledge_point_id=kp.id,
                    bloom_level=kp.bloom_level,
                    question_type=qtype,
                    question_text=item.get("question_text", ""),
                    reference_answer=item.get("reference_answer", ""),
                    project_id=getattr(kp, "project_id", None),
                    notebook_origin=getattr(kp, "notebook_origin", "user_project"),
                )
                db.add(q)
                questions.append(q)
            except Exception as e:
                logger.warning("compose_quiz LLM call failed for kp=%s: %s", kp.id, e)

        if not questions:
            await db.rollback()
            raise LLMError()

        session.question_count = len(questions)
        await db.commit()
        await db.refresh(session)
        return session

    async def _resolve_compose_kp_pool(
        self, db: AsyncSession, uid: uuid.UUID, data: ComposeQuizRequest,
    ) -> list[KnowledgePoint]:
        """组卷模式范围解析。优先级：tree_node_id > project_id > subject > kp_ids > 全部。"""
        if data.tree_node_id:
            node_result = await db.execute(
                select(ProjectTreeNode).where(ProjectTreeNode.id == data.tree_node_id)
            )
            node = node_result.scalar_one_or_none()
            if not node:
                raise NotFoundError("树节点不存在")
            kp_ids = []
            if node.kp_id:
                kp_ids.append(node.kp_id)
            # 递归收集子节点的 kp_id
            stack = [node.id]
            while stack:
                pid = stack.pop()
                child_q = await db.execute(
                    select(ProjectTreeNode).where(ProjectTreeNode.parent_id == pid)
                )
                for child in child_q.scalars().all():
                    if child.kp_id:
                        kp_ids.append(child.kp_id)
                    stack.append(child.id)
            if not kp_ids:
                return []
            r = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.id.in_(kp_ids),
                    KnowledgePoint.user_id == uid,
                )
            )
            return list(r.scalars().all())

        if data.project_id:
            r = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.user_id == uid,
                    KnowledgePoint.project_id == data.project_id,
                )
            )
            return list(r.scalars().all())

        if data.knowledge_point_ids:
            r = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.user_id == uid,
                    KnowledgePoint.id.in_(data.knowledge_point_ids),
                )
            )
            return list(r.scalars().all())

        if data.subject:
            r = await db.execute(
                select(KnowledgePoint).where(
                    KnowledgePoint.user_id == uid,
                    KnowledgePoint.subject == data.subject,
                )
            )
            return list(r.scalars().all())

        # 兜底：用户所有 KP
        r = await db.execute(
            select(KnowledgePoint).where(KnowledgePoint.user_id == uid).limit(50)
        )
        return list(r.scalars().all())

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

        score, feedback, is_wrong, error_reason = await self._grade_answer(question, data.user_answer)

        question.user_answer = data.user_answer
        question.ai_score = score
        question.ai_feedback = feedback
        question.is_wrong = is_wrong
        question.error_reason = error_reason  # v0.34 P1-5
        question.answered_at = datetime.now(timezone.utc)

        session.answered_count += 1

        # v0.34 P1-2 · 自适应难度：更新用户技能等级（按学科）
        try:
            if session.subject:
                from app.services.skill_level_service import update_after_answer
                level_change = await update_after_answer(
                    db,
                    user_id=uuid.UUID(user_id),
                    subject=session.subject,
                    is_correct=not is_wrong,
                )
                if level_change["changed"]:
                    logger.info(
                        f"skill level changed for u={user_id} {session.subject}: "
                        f"{level_change['prev_bloom']} → {level_change['new_bloom']}"
                    )
        except Exception as _e:
            logger.warning(f"skill_level update failed: {_e}")

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

        # v0.26 · 自动写入 SS 时间线（PRD 行 438 第 4/5 类）
        # v0.27 Q-05 · 优先用 TrainingSession 上挂的 ss_session_id（若有），否则 fallback active
        try:
            from app.services.ss_timeline_service import (
                ss_timeline_service, find_active_ss_session_id,
            )
            ss_id = getattr(session, "ss_session_id", None)
            if ss_id is None:
                ss_id = await find_active_ss_session_id(db, uuid.UUID(user_id))
            if ss_id is not None:
                # training_result 节点
                await ss_timeline_service.append_system_node(
                    db,
                    session_id=ss_id,
                    user_id=uuid.UUID(user_id),
                    kind="training_result",
                    title=f"训练答题 · {question.bloom_level}",
                    content=question.question_text[:200],
                    payload={
                        "question_id": str(question.id),
                        "ai_score": score,
                        "is_wrong": is_wrong,
                        "question_type": question.question_type,
                    },
                    ref_training_question_id=question.id,
                    ref_kp_id=question.knowledge_point_id,
                )
                # 若答错，再写 mistake 节点
                if is_wrong:
                    await ss_timeline_service.append_system_node(
                        db,
                        session_id=ss_id,
                        user_id=uuid.UUID(user_id),
                        kind="mistake",
                        title="错题 · 加入复习队列",
                        content=question.question_text[:200],
                        payload={
                            "question_id": str(question.id),
                            "user_answer": (data.user_answer or "")[:300],
                            "reference": (question.reference_answer or "")[:300],
                        },
                        ref_training_question_id=question.id,
                        ref_kp_id=question.knowledge_point_id,
                    )
                await db.commit()
        except Exception as e:
            logger.warning(f"SS timeline write (training) failed: {e}")

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

    async def _grade_answer(
        self, question: TrainingQuestion, user_answer: str,
    ) -> tuple[int, str, bool, str | None]:
        """v0.34 P1-5 · 返回多 1 个 error_reason"""
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
            error_reason = data.get("error_reason")
            if error_reason not in ("careless", "concept", "method"):
                error_reason = None
            if not is_wrong:
                error_reason = None
            return score, feedback, is_wrong, error_reason
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
