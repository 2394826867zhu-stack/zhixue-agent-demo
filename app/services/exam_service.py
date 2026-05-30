import uuid
import logging
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.exam import Exam
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion
from app.schemas.exam import ExamCreate, ExamUpdate, ExamOut, CountdownItem, CountdownOut
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.llm.client import llm_client
from app.llm.prompts.exam_tip import exam_tip_prompt

logger = logging.getLogger(__name__)


class ExamService:

    async def create_exam(self, db: AsyncSession, user_id: str, data: ExamCreate) -> Exam:
        uid = uuid.UUID(user_id)
        exam = Exam(
            user_id=uid,
            name=data.name,
            subject=data.subject,
            exam_date=data.exam_date,
            notes=data.notes,
        )
        db.add(exam)
        await db.commit()
        await db.refresh(exam)
        return exam

    async def list_exams(
        self,
        db: AsyncSession,
        user_id: str,
        include_past: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Exam], int]:
        uid = uuid.UUID(user_id)
        base = select(Exam).where(Exam.user_id == uid)
        if not include_past:
            base = base.where(Exam.exam_date >= date.today())
        total = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        q = (
            base.order_by(Exam.exam_date.asc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await db.execute(q)
        return list(result.scalars().all()), total

    async def get_exam(self, db: AsyncSession, exam_id: str, user_id: str) -> Exam:
        """v0.32 · 单条详情"""
        return await self._get_exam(db, exam_id, user_id)

    async def update_exam(self, db: AsyncSession, exam_id: str, user_id: str, data: ExamUpdate) -> Exam:
        exam = await self._get_exam(db, exam_id, user_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(exam, field, value)
        await db.commit()
        await db.refresh(exam)
        return exam

    async def delete_exam(self, db: AsyncSession, exam_id: str, user_id: str) -> None:
        exam = await self._get_exam(db, exam_id, user_id)
        await db.delete(exam)
        await db.commit()

    async def get_countdown(self, db: AsyncSession, user_id: str) -> CountdownOut:
        uid = uuid.UUID(user_id)
        today = date.today()

        # 最近5场未来考试（含今天）
        result = await db.execute(
            select(Exam)
            .where(Exam.user_id == uid, Exam.exam_date >= today)
            .order_by(Exam.exam_date.asc())
            .limit(5)
        )
        exams = list(result.scalars().all())

        if not exams:
            return CountdownOut(upcoming=[], has_exam_today=False)

        has_exam_today = exams[0].exam_date == today

        # 为最近一场考试生成 AI 建议
        nearest = exams[0]
        nearest_out = ExamOut.model_validate(nearest)
        ai_tip = await self._gen_tip(db, uid, nearest_out)

        items: list[CountdownItem] = []
        for i, exam in enumerate(exams):
            exam_out = ExamOut.model_validate(exam)
            items.append(CountdownItem(
                exam=exam_out,
                ai_tip=ai_tip if i == 0 else None,
            ))

        return CountdownOut(upcoming=items, has_exam_today=has_exam_today)

    # ---------- 内部工具 ----------

    async def _get_exam(self, db: AsyncSession, exam_id: str, user_id: str) -> Exam:
        result = await db.execute(
            select(Exam).where(Exam.id == uuid.UUID(exam_id))
        )
        exam = result.scalar_one_or_none()
        if not exam:
            raise NotFoundError("考试不存在")
        if str(exam.user_id) != user_id:
            raise PermissionDeniedError("无权操作此考试")
        return exam

    async def _gen_tip(self, db: AsyncSession, uid: uuid.UUID, exam: ExamOut) -> str | None:
        try:
            # 该学科知识点掌握情况
            kp_rows = await db.execute(
                select(KnowledgePoint.mastery_status, func.count())
                .where(
                    KnowledgePoint.user_id == uid,
                    *([] if not exam.subject else [KnowledgePoint.subject == exam.subject]),
                )
                .group_by(KnowledgePoint.mastery_status)
            )
            kp_dist = {r[0]: r[1] for r in kp_rows}
            total_kps = sum(kp_dist.values())
            mastered_kps = kp_dist.get("mastered", 0)

            # 近期错误频繁的学科（top3）
            wrong_rows = await db.execute(
                select(KnowledgePoint.subject, func.count(TrainingQuestion.id).label("cnt"))
                .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
                .where(
                    TrainingQuestion.user_id == uid,
                    TrainingQuestion.is_wrong == True,
                    TrainingQuestion.is_retry == False,
                )
                .group_by(KnowledgePoint.subject)
                .order_by(func.count(TrainingQuestion.id).desc())
                .limit(3)
            )
            weak_subjects = [r[0] for r in wrong_rows if r[0]]

            system, prompt = exam_tip_prompt(
                exam_name=exam.name,
                subject=exam.subject,
                days_remaining=exam.days_remaining,
                mastered_kps=mastered_kps,
                total_kps=total_kps,
                weak_subjects=weak_subjects,
            )
            tip = await llm_client.generate(prompt, system=system)
            return tip.strip()
        except Exception as e:
            logger.warning(f"exam tip generation failed: {e}")
            return None


exam_service = ExamService()
