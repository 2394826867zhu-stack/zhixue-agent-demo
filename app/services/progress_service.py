import uuid
import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case

from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.models.training import TrainingQuestion
from app.models.task import DailyTask, PomodoroRecord

logger = logging.getLogger(__name__)


class ProgressService:

    async def get_overview(self, db: AsyncSession, user_id: str) -> dict:
        uid = uuid.UUID(user_id)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        # mastery distribution
        mastery_rows = await db.execute(
            select(KnowledgePoint.mastery_status, func.count())
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.mastery_status)
        )
        dist = {r[0]: r[1] for r in mastery_rows}
        total_kp = sum(dist.values())

        # today tasks
        today_tasks = await db.execute(
            select(
                func.count().label("total"),
                func.count(case((DailyTask.status == "done", 1))).label("done"),
            ).where(DailyTask.user_id == uid, DailyTask.task_date == today)
        )
        tt = today_tasks.one()

        # week pomodoro
        week_pomo = await db.execute(
            select(func.count(), func.sum(PomodoroRecord.duration_minutes))
            .where(PomodoroRecord.user_id == uid, PomodoroRecord.record_date >= week_start)
        )
        wp = week_pomo.one()

        # total wrong (not yet resolved)
        wrong_result = await db.execute(
            select(func.count()).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
            )
        )

        # total flashcards
        fc_result = await db.execute(
            select(func.count()).where(Flashcard.user_id == uid)
        )

        return {
            "total_kp": total_kp,
            "mastery_distribution": {
                "new": dist.get("new", 0),
                "learning": dist.get("learning", 0),
                "reviewing": dist.get("reviewing", 0),
                "mastered": dist.get("mastered", 0),
            },
            "today_tasks_total": tt[0] or 0,
            "today_tasks_done": tt[1] or 0,
            "week_pomodoro_count": wp[0] or 0,
            "week_study_minutes": wp[1] or 0,
            "total_wrong": wrong_result.scalar() or 0,
            "total_flashcards": fc_result.scalar() or 0,
        }

    async def get_heatmap(self, db: AsyncSession, user_id: str, days: int = 90) -> list[dict]:
        uid = uuid.UUID(user_id)
        start_date = date.today() - timedelta(days=days - 1)

        rows = await db.execute(
            select(PomodoroRecord.record_date, func.sum(PomodoroRecord.duration_minutes))
            .where(PomodoroRecord.user_id == uid, PomodoroRecord.record_date >= start_date)
            .group_by(PomodoroRecord.record_date)
            .order_by(PomodoroRecord.record_date.asc())
        )
        by_date = {str(r[0]): r[1] for r in rows}

        result = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            result.append({"date": str(d), "minutes": by_date.get(str(d), 0)})
        return result

    async def get_subjects(self, db: AsyncSession, user_id: str) -> list[dict]:
        uid = uuid.UUID(user_id)

        subject_rows = await db.execute(
            select(
                KnowledgePoint.subject,
                func.count().label("kp_count"),
                func.count(case((KnowledgePoint.mastery_status == "mastered", 1))).label("mastered_count"),
            )
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.subject)
            .order_by(func.count().desc())
        )

        result = []
        for row in subject_rows:
            subject, kp_count, mastered_count = row
            mastery_rate = round(mastered_count / kp_count * 100, 1) if kp_count else 0.0

            fc_result = await db.execute(
                select(func.count(Flashcard.id))
                .join(KnowledgePoint, Flashcard.knowledge_point_id == KnowledgePoint.id)
                .where(
                    Flashcard.user_id == uid,
                    KnowledgePoint.subject == subject if subject else KnowledgePoint.subject.is_(None),
                )
            )

            wrong_result = await db.execute(
                select(func.count(TrainingQuestion.id))
                .join(KnowledgePoint, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
                .where(
                    TrainingQuestion.user_id == uid,
                    TrainingQuestion.is_wrong == True,
                    TrainingQuestion.is_retry == False,
                    KnowledgePoint.subject == subject if subject else KnowledgePoint.subject.is_(None),
                )
            )

            result.append({
                "subject": subject or "未分类",
                "kp_count": kp_count,
                "mastered_count": mastered_count,
                "mastery_rate": mastery_rate,
                "flashcard_count": fc_result.scalar() or 0,
                "wrong_count": wrong_result.scalar() or 0,
            })

        return result

    async def get_weekly_report(self, db: AsyncSession, user_id: str, offset_weeks: int = 0) -> dict:
        """offset_weeks=0 → this week, 1 → last week"""
        uid = uuid.UUID(user_id)
        today = date.today()
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=offset_weeks)
        week_end = week_start + timedelta(days=6)

        # new KPs this week
        new_kp = await db.execute(
            select(func.count()).where(
                KnowledgePoint.user_id == uid,
                func.date(KnowledgePoint.created_at) >= week_start,
                func.date(KnowledgePoint.created_at) <= week_end,
            )
        )
        new_kp_count = new_kp.scalar() or 0

        # flashcard completion rate: reviewed this week / due this week
        due_this_week = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == uid,
                Flashcard.due_date >= week_start,
                Flashcard.due_date <= week_end,
            )
        )
        reviewed_this_week = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == uid,
                func.date(Flashcard.last_review) >= week_start,
                func.date(Flashcard.last_review) <= week_end,
            )
        )
        due_cnt = due_this_week.scalar() or 0
        reviewed_cnt = reviewed_this_week.scalar() or 0
        fc_rate = round(reviewed_cnt / due_cnt * 100, 1) if due_cnt else 0.0

        # avg training score this week
        score_result = await db.execute(
            select(func.avg(TrainingQuestion.ai_score)).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.ai_score.isnot(None),
                func.date(TrainingQuestion.answered_at) >= week_start,
                func.date(TrainingQuestion.answered_at) <= week_end,
            )
        )
        avg_score_raw = score_result.scalar()
        avg_score = round(float(avg_score_raw), 1) if avg_score_raw else None

        # wrong count (total unresolved)
        wrong_result = await db.execute(
            select(func.count()).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
            )
        )
        wrong_count = wrong_result.scalar() or 0

        # pomodoro stats
        pomo_result = await db.execute(
            select(func.count(), func.sum(PomodoroRecord.duration_minutes))
            .where(
                PomodoroRecord.user_id == uid,
                PomodoroRecord.record_date >= week_start,
                PomodoroRecord.record_date <= week_end,
            )
        )
        pr = pomo_result.one()
        pomo_count = pr[0] or 0
        study_minutes = pr[1] or 0

        # weak subjects (most wrong questions)
        weak_rows = await db.execute(
            select(KnowledgePoint.subject, func.count(TrainingQuestion.id))
            .join(TrainingQuestion, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
            .where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
                KnowledgePoint.subject.isnot(None),
            )
            .group_by(KnowledgePoint.subject)
            .order_by(func.count(TrainingQuestion.id).desc())
            .limit(3)
        )
        weak_subjects = [r[0] for r in weak_rows]

        # weak KPs (lowest mastery, non-mastered)
        weak_kp_rows = await db.execute(
            select(KnowledgePoint.name)
            .where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.mastery_status.in_(["new", "learning"]),
            )
            .order_by(KnowledgePoint.updated_at.asc())
            .limit(3)
        )
        weak_kps = [r[0] for r in weak_kp_rows]

        ai_advice = await self._generate_advice(
            new_kp_count, fc_rate, avg_score, wrong_count,
            study_minutes, pomo_count, weak_subjects, weak_kps
        )

        return {
            "week_start": str(week_start),
            "week_end": str(week_end),
            "new_kp_count": new_kp_count,
            "flashcard_completion_rate": fc_rate,
            "avg_training_score": avg_score,
            "wrong_count": wrong_count,
            "pomodoro_count": pomo_count,
            "study_minutes": study_minutes,
            "weak_subjects": weak_subjects,
            "ai_advice": ai_advice,
        }

    async def _generate_advice(
        self, new_kp: int, fc_rate: float, avg_score: float | None,
        wrong: int, minutes: int, pomo: int,
        weak_subjects: list[str], weak_kps: list[str]
    ) -> str:
        from app.llm.client import llm_client
        from app.llm.prompts.progress_prompts import WEEKLY_ADVICE_PROMPT, SYSTEM_PROGRESS

        try:
            raw = await llm_client.generate(
                WEEKLY_ADVICE_PROMPT.format(
                    new_kp_count=new_kp,
                    flashcard_completion_rate=fc_rate,
                    avg_training_score=avg_score if avg_score is not None else "暂无",
                    wrong_count=wrong,
                    study_minutes=minutes,
                    pomodoro_count=pomo,
                    weak_subjects="、".join(weak_subjects) if weak_subjects else "暂无",
                    weak_kps="、".join(weak_kps) if weak_kps else "暂无",
                ),
                system=SYSTEM_PROGRESS,
            )
            return raw.strip()
        except Exception as e:
            logger.warning(f"Weekly advice generation failed: {e}")
            if weak_subjects:
                return f"本周学习数据已汇总。建议重点复习{weak_subjects[0]}，加强错题重练，保持每日学习节奏。"
            return "本周学习数据已汇总。建议持续保持学习节奏，重点攻克薄弱知识点，坚持使用闪卡复习。"


progress_service = ProgressService()
