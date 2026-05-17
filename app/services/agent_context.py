import uuid
import logging
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.knowledge_point import KnowledgePoint
from app.models.task import DailyTask, PomodoroRecord
from app.models.exam import Exam
from app.models.checkin import CheckIn
from app.llm.prompts.agent import AgentContext

logger = logging.getLogger(__name__)

GRADE_DISPLAY = {
    "junior_1": "初一", "junior_2": "初二", "junior_3": "初三",
    "senior_1": "高一", "senior_2": "高二", "senior_3": "高三",
    "university": "大学",
}


async def load_user_context(db: AsyncSession, user_id: str) -> AgentContext:
    uid = uuid.UUID(user_id)

    # 1. 用户基础信息
    user_row = await db.execute(select(User).where(User.id == uid))
    user = user_row.scalar_one_or_none()
    username = user.username if user else "同学"
    grade_raw = user.grade if user else ""
    grade = GRADE_DISPLAY.get(grade_raw, grade_raw)
    profile = user.learning_profile or {}
    subjects = profile.get("subjects", [])

    # 2. 今日任务统计
    today = date.today()
    task_rows = await db.execute(
        select(DailyTask).where(
            DailyTask.user_id == uid,
            DailyTask.task_date == today,
        )
    )
    today_tasks = task_rows.scalars().all()
    done_tasks = sum(1 for t in today_tasks if t.status == "done")
    total_tasks = len(today_tasks)

    # 3. 连续学习天数（按番茄钟记录逆推）
    streak_days = await _calc_streak(db, uid)

    # 4. 最近一场未来考试
    exam_row = await db.execute(
        select(Exam)
        .where(Exam.user_id == uid, Exam.exam_date >= today)
        .order_by(Exam.exam_date.asc())
        .limit(1)
    )
    exam = exam_row.scalar_one_or_none()
    upcoming_exam_name = exam.name if exam else None
    days_remaining = (exam.exam_date - today).days if exam else None

    # 5. 最弱科目（learning 状态 KP 最多的科目）
    kp_stat = await db.execute(
        select(KnowledgePoint.subject, func.count(KnowledgePoint.id).label("cnt"))
        .where(
            KnowledgePoint.user_id == uid,
            KnowledgePoint.mastery_status == "learning",
            KnowledgePoint.subject.isnot(None),
        )
        .group_by(KnowledgePoint.subject)
        .order_by(func.count(KnowledgePoint.id).desc())
        .limit(1)
    )
    weakest_row = kp_stat.one_or_none()
    weakest_subject = weakest_row[0] if weakest_row else None
    learning_count = weakest_row[1] if weakest_row else 0

    # 6. 今日签到摘要（可选）
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    checkin_row = await db.execute(
        select(CheckIn)
        .where(CheckIn.user_id == uid, CheckIn.created_at >= today_start)
        .order_by(CheckIn.created_at.desc())
        .limit(1)
    )
    checkin = checkin_row.scalar_one_or_none()
    checkin_summary = checkin.ai_summary if checkin else None

    return AgentContext(
        username=username,
        grade=grade,
        subjects=subjects,
        streak_days=streak_days,
        done_tasks=done_tasks,
        total_tasks=total_tasks,
        upcoming_exam_name=upcoming_exam_name,
        days_remaining=days_remaining,
        weakest_subject=weakest_subject,
        learning_count=learning_count,
        checkin_summary=checkin_summary,
    )


async def _calc_streak(db: AsyncSession, uid: uuid.UUID) -> int:
    """逆推连续学习天数：有番茄钟记录的天数连续多少天"""
    rows = await db.execute(
        select(func.date(PomodoroRecord.started_at).label("d"))
        .where(PomodoroRecord.user_id == uid)
        .distinct()
        .order_by(func.date(PomodoroRecord.started_at).desc())
        .limit(60)
    )
    days = [r[0] for r in rows.all()]
    if not days:
        return 0
    streak = 0
    check = date.today()
    for d in days:
        if d == check:
            streak += 1
            check = check - timedelta(days=1)
        else:
            break
    return streak
