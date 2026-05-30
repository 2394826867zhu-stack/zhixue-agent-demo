"""v0.29 Memory · Celery beat 扫描任务

scan_inactive_users:   连续 N 天未学 → 写 inactive_streak（Q5）
scan_upcoming_exams:   考试 < 7 天 → 写 exam_approaching（Q5）
cleanup_old_episodes:  Q6 锁定 90d + importance<7 清理
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.memory_tasks.scan_inactive_users")
def scan_inactive_users(threshold_days: int = 3):
    """连续 N 天未学 → 写 inactive_streak episode（去重 1d）"""
    _run(_scan_inactive_async(threshold_days))


async def _scan_inactive_async(threshold_days: int):
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.task import PomodoroRecord
    from app.models.checkin import CheckIn
    from app.models.flashcard import Flashcard
    from app.services.episodic_memory_service import record_event
    from app.models.agent_episode import AgentEpisode
    from sqlalchemy import select, func, or_

    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)

    async with AsyncSessionLocal() as db:
        # 候选：所有未删用户
        all_users = (await db.execute(select(User.id))).scalars().all()
        count = 0
        for uid in all_users:
            # 判断活跃度：近 threshold_days 内有任何学习动作？
            recent_q = await db.execute(
                select(func.count()).where(
                    PomodoroRecord.user_id == uid,
                    PomodoroRecord.created_at >= cutoff,
                )
            )
            if recent_q.scalar_one() > 0:
                continue
            recent_q = await db.execute(
                select(func.count()).where(
                    CheckIn.user_id == uid,
                    CheckIn.created_at >= cutoff,
                )
            )
            if recent_q.scalar_one() > 0:
                continue
            recent_q = await db.execute(
                select(func.count()).where(
                    Flashcard.user_id == uid,
                    Flashcard.last_review >= cutoff,
                )
            )
            if recent_q.scalar_one() > 0:
                continue

            # 去重：1 天内已记过同类 episode 则跳过
            dedup_q = await db.execute(
                select(func.count()).where(
                    AgentEpisode.user_id == uid,
                    AgentEpisode.event_kind == "inactive_streak",
                    AgentEpisode.occurred_at >= datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
            if dedup_q.scalar_one() > 0:
                continue

            try:
                await record_event(
                    db, user_id=uid, event_kind="inactive_streak",
                    summary=f"用户已连续 {threshold_days} 天没有学习动作。",
                    detail={"threshold_days": threshold_days},
                    importance=7,
                    emotional_tone="negative",
                )
                count += 1
            except Exception as e:
                logger.warning(f"inactive episode record failed for {uid}: {e}")
        logger.info(f"scan_inactive_users: recorded {count} episodes")


@celery_app.task(name="app.tasks.memory_tasks.scan_upcoming_exams")
def scan_upcoming_exams(threshold_days: int = 7):
    """考试 < N 天 → 写 exam_approaching episode（每场考试只记一次）"""
    _run(_scan_exams_async(threshold_days))


async def _scan_exams_async(threshold_days: int):
    from app.core.database import AsyncSessionLocal
    from app.models.exam import Exam
    from app.models.agent_episode import AgentEpisode
    from app.services.episodic_memory_service import record_event
    from sqlalchemy import select, func, and_
    from datetime import date

    today = date.today()
    deadline = today + timedelta(days=threshold_days)

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Exam).where(
                Exam.exam_date >= today,
                Exam.exam_date <= deadline,
            )
        )
        count = 0
        for exam in rows.scalars().all():
            # 去重：本场考试已记过则跳
            dedup_q = await db.execute(
                select(func.count()).where(
                    AgentEpisode.user_id == exam.user_id,
                    AgentEpisode.event_kind == "exam_approaching",
                    AgentEpisode.detail["exam_id"].astext == str(exam.id),
                )
            )
            if dedup_q.scalar_one() > 0:
                continue
            days_left = (exam.exam_date - today).days
            try:
                await record_event(
                    db, user_id=exam.user_id, event_kind="exam_approaching",
                    summary=f"考试「{exam.name}」还有 {days_left} 天（{exam.exam_date}）。",
                    detail={"exam_id": str(exam.id), "exam_name": exam.name,
                            "days_left": days_left, "subject": exam.subject},
                    importance=8 if days_left <= 3 else 7,
                    emotional_tone="negative" if days_left <= 3 else "neutral",
                )
                count += 1
            except Exception as e:
                logger.warning(f"exam_approaching record failed: {e}")
        logger.info(f"scan_upcoming_exams: recorded {count} episodes")


@celery_app.task(name="app.tasks.memory_tasks.cleanup_old_episodes")
def cleanup_old_episodes_task(days: int = 90):
    """Q6 锁定 · 90 天前的 importance<7 episodes 清理"""
    _run(_cleanup_async(days))


async def _cleanup_async(days: int):
    from app.core.database import AsyncSessionLocal
    from app.services.episodic_memory_service import cleanup_old_episodes
    async with AsyncSessionLocal() as db:
        n = await cleanup_old_episodes(db, days=days)
        logger.info(f"cleanup_old_episodes: removed {n} rows")
