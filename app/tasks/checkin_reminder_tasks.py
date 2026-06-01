"""C-20 · 每日打卡提醒

调度：Celery beat 每小时 :50 分。
规则：
  - user.daily_reminder_enabled = True
  - user.daily_reminder_time 与当前北京时间小时匹配
  - 今日尚未打卡
  - 23h 去重（防止同日重复推送）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_NOTIF_TYPE = "daily_checkin_reminder"
_DEDUP_HOURS = 23


def should_send_checkin_reminder(
    daily_reminder_enabled: bool,
    daily_reminder_time: str | None,
    current_bj_hour: int,
    checked_in_today: bool,
    hours_since_last_reminder: float | None,
) -> bool:
    """Pure guard — no DB, fully testable."""
    if not daily_reminder_enabled or not daily_reminder_time:
        return False
    if checked_in_today:
        return False
    if hours_since_last_reminder is not None and hours_since_last_reminder < _DEDUP_HOURS:
        return False
    try:
        target_hour = int(daily_reminder_time.split(":")[0])
    except (ValueError, IndexError, AttributeError):
        return False
    return current_bj_hour == target_hour


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.checkin_reminder_tasks.scan_checkin_reminder")
def scan_checkin_reminder():
    """每小时扫描：用户设定时间到 → 未打卡 → 推送提醒"""
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.checkin import CheckIn
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    now = datetime.now(timezone.utc)
    bj_now = now + timedelta(hours=8)
    current_bj_hour = bj_now.hour
    today_bj = bj_now.date()
    today_start_utc = datetime(today_bj.year, today_bj.month, today_bj.day,
                               tzinfo=timezone.utc) - timedelta(hours=8)

    pushed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        users_result = await db.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.daily_reminder_enabled.is_(True),
                User.daily_reminder_time.isnot(None),
                User.push_enabled.is_(True),
                User.expo_push_token.isnot(None),
            )
        )
        users = list(users_result.scalars().all())

    notif_svc = NotificationService()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                # Checked in today?
                checkin_result = await db.execute(
                    select(func.count()).select_from(CheckIn).where(
                        CheckIn.user_id == user.id,
                        CheckIn.created_at >= today_start_utc,
                    )
                )
                checked_in = int(checkin_result.scalar_one() or 0) > 0

                # Hours since last reminder
                last_result = await db.execute(
                    select(func.max(Notification.created_at)).where(
                        Notification.user_id == user.id,
                        Notification.notification_type == _NOTIF_TYPE,
                    )
                )
                last_at = last_result.scalar_one()
                if last_at is not None:
                    if last_at.tzinfo is None:
                        last_at = last_at.replace(tzinfo=timezone.utc)
                    hours_since = (now - last_at).total_seconds() / 3600
                else:
                    hours_since = None

                if not should_send_checkin_reminder(
                    user.daily_reminder_enabled,
                    user.daily_reminder_time,
                    current_bj_hour,
                    checked_in,
                    hours_since,
                ):
                    skipped += 1
                    continue

                await notif_svc.create(
                    db,
                    user_id=str(user.id),
                    content="今天还没打卡，趁现在记录一下学了什么",
                    notification_type=_NOTIF_TYPE,
                    related_action="/checkin",
                )
                pushed += 1
        except Exception as exc:
            logger.warning(f"checkin_reminder failed for user {user.id}: {exc}")
            skipped += 1

    logger.info(f"scan_checkin_reminder: pushed={pushed} skipped={skipped}")
    return {"pushed": pushed, "skipped": skipped}
