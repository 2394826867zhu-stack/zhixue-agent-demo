import uuid
import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.checkin import CheckIn
from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.models.training import TrainingQuestion
from app.models.task import PomodoroRecord
from app.schemas.reports import MasteryDistribution, WeeklyReportOut

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helper functions (no DB, fully testable)
# ---------------------------------------------------------------------------

def classify_p_mastery(p: float | None) -> str:
    """Returns 'struggling', 'learning', 'mastered', or 'unprobed'."""
    if p is None:
        return "unprobed"
    if p < 0.3:
        return "struggling"
    if p <= 0.7:
        return "learning"
    return "mastered"


def build_mastery_distribution(
    p_mastery_values: list[float | None],
) -> tuple[MasteryDistribution, float | None]:
    """Returns (MasteryDistribution, avg_p_mastery|None)."""
    counts = {"struggling": 0, "learning": 0, "mastered": 0, "unprobed": 0}
    non_none: list[float] = []
    for p in p_mastery_values:
        label = classify_p_mastery(p)
        counts[label] += 1
        if p is not None:
            non_none.append(p)
    avg = round(sum(non_none) / len(non_none), 4) if non_none else None
    return (
        MasteryDistribution(
            struggling=counts["struggling"],
            learning=counts["learning"],
            mastered=counts["mastered"],
            unprobed=counts["unprobed"],
        ),
        avg,
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class ReportsService:

    async def get_weekly_report(
        self,
        db: AsyncSession,
        user_id: str,
        offset_weeks: int = 0,
    ) -> WeeklyReportOut:
        uid = uuid.UUID(user_id)
        today = date.today()
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=offset_weeks)
        week_end = week_start + timedelta(days=6)

        # 1. Check-ins this week
        checkin_rows = await db.execute(
            select(CheckIn.ai_summary).where(
                CheckIn.user_id == uid,
                func.date(CheckIn.created_at) >= week_start,
                func.date(CheckIn.created_at) <= week_end,
            )
        )
        checkins = checkin_rows.scalars().all()
        checkin_count = len(checkins)
        checkin_summaries = [s for s in checkins if s]

        # 2. New knowledge points this week
        new_kp_result = await db.execute(
            select(func.count()).where(
                KnowledgePoint.user_id == uid,
                func.date(KnowledgePoint.created_at) >= week_start,
                func.date(KnowledgePoint.created_at) <= week_end,
            )
        )
        new_kps = new_kp_result.scalar() or 0

        # 3. Flashcard completion rate
        due_result = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == uid,
                Flashcard.due_date >= week_start,
                Flashcard.due_date <= week_end,
            )
        )
        reviewed_result = await db.execute(
            select(func.count()).where(
                Flashcard.user_id == uid,
                func.date(Flashcard.last_review) >= week_start,
                func.date(Flashcard.last_review) <= week_end,
            )
        )
        due_count = due_result.scalar() or 0
        reviewed_count = reviewed_result.scalar() or 0
        flashcard_completion_rate = (
            round(reviewed_count / due_count * 100, 1) if due_count > 0 else 0.0
        )

        # 4. Training avg score this week
        score_result = await db.execute(
            select(func.avg(TrainingQuestion.ai_score)).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.ai_score.isnot(None),
                func.date(TrainingQuestion.answered_at) >= week_start,
                func.date(TrainingQuestion.answered_at) <= week_end,
            )
        )
        avg_score_raw = score_result.scalar()
        training_avg_score = round(float(avg_score_raw), 1) if avg_score_raw is not None else None

        # 5. Wrong count (all-time, not-retried)
        wrong_result = await db.execute(
            select(func.count()).where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
            )
        )
        wrong_count = wrong_result.scalar() or 0

        # 6. Pomodoro this week
        pomo_result = await db.execute(
            select(func.count(), func.sum(PomodoroRecord.duration_minutes)).where(
                PomodoroRecord.user_id == uid,
                PomodoroRecord.record_date >= week_start,
                PomodoroRecord.record_date <= week_end,
            )
        )
        pr = pomo_result.one()
        pomodoro_count = pr[0] or 0
        total_minutes = pr[1] or 0

        # 7. Mastery distribution (all KPs for this user)
        mastery_rows = await db.execute(
            select(KnowledgePoint.p_mastery).where(KnowledgePoint.user_id == uid)
        )
        p_mastery_values: list[float | None] = list(mastery_rows.scalars().all())
        mastery_distribution, avg_p_mastery = build_mastery_distribution(p_mastery_values)

        # 8. Weak subjects (top 3 by wrong count)
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

        # 9. Weakest KPs by p_mastery (lowest 3 probed KPs)
        weak_kp_rows = await db.execute(
            select(KnowledgePoint.name).where(
                KnowledgePoint.user_id == uid,
                KnowledgePoint.p_mastery.isnot(None),
            )
            .order_by(KnowledgePoint.p_mastery.asc())
            .limit(3)
        )
        weak_kp_names = [r[0] for r in weak_kp_rows]

        # 10. AI advice
        ai_advice = await self._generate_advice(
            new_kps=new_kps,
            checkin_count=checkin_count,
            checkin_summaries=checkin_summaries,
            flashcard_completion_rate=flashcard_completion_rate,
            training_avg_score=training_avg_score,
            wrong_count=wrong_count,
            total_minutes=total_minutes,
            pomodoro_count=pomodoro_count,
            mastery_distribution=mastery_distribution,
            weak_subjects=weak_subjects,
            weak_kp_names=weak_kp_names,
        )

        return WeeklyReportOut(
            week_start=str(week_start),
            week_end=str(week_end),
            new_kps=new_kps,
            flashcard_completion_rate=flashcard_completion_rate,
            training_avg_score=training_avg_score,
            wrong_count=wrong_count,
            pomodoro_count=pomodoro_count,
            total_minutes=total_minutes,
            checkin_count=checkin_count,
            mastery_distribution=mastery_distribution,
            avg_p_mastery=avg_p_mastery,
            weak_subjects=weak_subjects,
            weak_kp_names=weak_kp_names,
            ai_advice=ai_advice,
        )

    async def _generate_advice(
        self,
        new_kps: int,
        checkin_count: int,
        checkin_summaries: list[str],
        flashcard_completion_rate: float,
        training_avg_score: float | None,
        wrong_count: int,
        total_minutes: int,
        pomodoro_count: int,
        mastery_distribution: MasteryDistribution,
        weak_subjects: list[str],
        weak_kp_names: list[str],
    ) -> str:
        from app.llm.client import llm_client
        from app.llm.prompts.progress_prompts import WEEKLY_REPORT_SYSTEM, WEEKLY_REPORT_PROMPT

        checkin_summaries_str = "；".join(checkin_summaries) if checkin_summaries else "无"
        training_avg_score_str = str(training_avg_score) if training_avg_score is not None else "暂无"
        weak_subjects_str = "、".join(weak_subjects) if weak_subjects else "暂无"
        weak_kp_names_str = "、".join(weak_kp_names) if weak_kp_names else "暂无"

        prompt = WEEKLY_REPORT_PROMPT.format(
            new_kps=new_kps,
            checkin_count=checkin_count,
            checkin_summaries=checkin_summaries_str,
            flashcard_completion_rate=flashcard_completion_rate,
            training_avg_score=training_avg_score_str,
            wrong_count=wrong_count,
            total_minutes=total_minutes,
            pomodoro_count=pomodoro_count,
            mastered=mastery_distribution.mastered,
            learning=mastery_distribution.learning,
            struggling=mastery_distribution.struggling,
            weak_subjects=weak_subjects_str,
            weak_kps=weak_kp_names_str,
        )

        try:
            raw = await llm_client.generate(prompt, system=WEEKLY_REPORT_SYSTEM)
            return raw.strip()
        except Exception as e:
            logger.warning(f"Weekly report AI advice generation failed: {e}")
            if weak_kp_names:
                return (
                    f"本周学习数据已汇总。建议重点复习{weak_kp_names[0]}等薄弱知识点，"
                    "加强错题重练，保持每日打卡节奏。"
                )
            return (
                "本周学习数据已汇总。建议持续保持学习节奏，坚持使用闪卡复习，重点攻克薄弱知识点。"
            )


reports_service = ReportsService()
