"""C-17/C-19 · FSRS 复习到期推送

调度：Celery beat 每小时 :30 分。
扫描规则：
  - 闪卡 due_date <= today
  - user.flashcard_reminder_enabled = True
  - 今日内未推过同类通知（8h 去重）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_NOTIF_TYPE = "fsrs_review_due"
_DEDUP_HOURS = 8


def should_send_review_reminder(
    due_count: int,
    flashcard_reminder_enabled: bool,
    hours_since_last_reminder: float | None,
) -> bool:
    """Pure guard — no DB, fully testable."""
    if not flashcard_reminder_enabled:
        return False
    if due_count <= 0:
        return False
    if hours_since_last_reminder is not None and hours_since_last_reminder < _DEDUP_HOURS:
        return False
    return True


def review_due_message(count: int) -> str:
    if count == 1:
        return "有1张复习卡今天到期了，顺手看一眼吧"
    elif count <= 10:
        return f"有{count}张复习卡今天到期了，别让它们积起来"
    else:
        return f"{count}张卡到期了，今天找个时间清一清"


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.review_due_tasks.scan_review_due")
def scan_review_due():
    """每小时扫描 FSRS 到期闪卡 → 推送复习提醒"""
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.flashcard import Flashcard
    from app.models.user import User
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    now = datetime.now(timezone.utc)
    today = date.today()
    cutoff = now - timedelta(hours=_DEDUP_HOURS)

    pushed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        # All users with push_enabled + flashcard_reminder_enabled + onboarding done + token
        users_result = await db.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.flashcard_reminder_enabled.is_(True),
                User.push_enabled.is_(True),
                User.expo_push_token.isnot(None),
            )
        )
        users = list(users_result.scalars().all())

    notif_svc = NotificationService()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                # Count due cards
                due_result = await db.execute(
                    select(func.count()).select_from(Flashcard).where(
                        Flashcard.user_id == user.id,
                        Flashcard.due_date <= today,
                    )
                )
                due_count = int(due_result.scalar_one() or 0)

                # Hours since last reminder of this type
                last_result = await db.execute(
                    select(func.max(Notification.created_at)).where(
                        Notification.user_id == user.id,
                        Notification.notification_type == _NOTIF_TYPE,
                    )
                )
                last_at = last_result.scalar_one()
                hours_since = (
                    (now - last_at).total_seconds() / 3600
                    if last_at and last_at.tzinfo
                    else None
                )

                if not should_send_review_reminder(due_count, user.flashcard_reminder_enabled, hours_since):
                    skipped += 1
                    continue

                await notif_svc.create(
                    db,
                    user_id=str(user.id),
                    content=review_due_message(due_count),
                    notification_type=_NOTIF_TYPE,
                    related_action="/flashcards",
                )
                pushed += 1
        except Exception as exc:
            logger.warning(f"review_due push failed for user {user.id}: {exc}")
            skipped += 1

    logger.info(f"scan_review_due: pushed={pushed} skipped={skipped}")
    return {"pushed": pushed, "skipped": skipped}
