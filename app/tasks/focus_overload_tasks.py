"""v0.34 P1-11 · 6h 学习时长软提醒

PRD 补全 · 未成年人保护 + 健康学习：单日累计学习时长 > 6h 时
Agent 推送一条"该休息了"提醒。

调度：Celery beat 每小时跑
判定：今日 pomodoro_records 累计 duration_minutes > 360
去重：今日已推过则不再推
"""
import asyncio
import logging
from datetime import datetime, timezone, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.focus_overload_tasks.scan_overload")
def scan_overload():
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.task import PomodoroRecord
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(PomodoroRecord.user_id,
                   func.coalesce(func.sum(PomodoroRecord.duration_minutes), 0).label("mins"))
            .where(PomodoroRecord.created_at >= today_start)
            .group_by(PomodoroRecord.user_id)
            .having(func.coalesce(func.sum(PomodoroRecord.duration_minutes), 0) > 360)
        )
        overloaded = [(row[0], row[1]) for row in rows.all()]

    if not overloaded:
        return {"pushed": 0}

    pushed = 0
    notif_svc = NotificationService()

    for uid, mins in overloaded:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(func.count()).where(
                    Notification.user_id == uid,
                    Notification.notification_type == "focus_overload",
                    Notification.created_at >= today_start,
                )
            )
            if existing.scalar_one() > 0:
                continue
            try:
                hours = round(mins / 60.0, 1)
                await notif_svc.create(
                    db,
                    user_id=str(uid),
                    content=f"今天专注了 {hours} 小时。学得够多了，去走两步。",
                    notification_type="focus_overload",
                    related_action="open_break",
                )
                pushed += 1
            except Exception as e:
                logger.warning(f"focus_overload push failed {uid}: {e}")

    logger.info(f"scan_overload: pushed {pushed} users")
    return {"pushed": pushed}
