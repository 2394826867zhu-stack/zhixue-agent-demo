import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.flashcard import Flashcard
from app.models.checkin import CheckIn
from app.models.exam import Exam
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationListResponse
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def _send_expo_push(token: str, body: str) -> None:
    """Fire-and-forget Expo push. Failures are logged, never raised."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={"to": token, "title": "知曜", "body": body, "sound": "default"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
    except Exception as e:
        logger.debug(f"Expo push failed: {e}")


class NotificationService:
    async def get_unread(self, db: AsyncSession, user_id: str) -> NotificationListResponse:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == uid, Notification.is_read == False)
            .order_by(Notification.created_at.desc())
            .limit(10)
        )
        items = list(result.scalars().all())
        return NotificationListResponse(
            items=[NotificationOut.model_validate(n) for n in items],
            unread_count=len(items),
        )

    async def get_all(
        self, db: AsyncSession, user_id: str, page: int = 1, page_size: int = 20
    ) -> NotificationListResponse:
        uid = uuid.UUID(user_id)
        # Single query: count total + unread using CASE (portable across dialects)
        from sqlalchemy import case as sa_case
        counts_result = await db.execute(
            select(
                func.count().label("total"),
                func.sum(sa_case((Notification.is_read == False, 1), else_=0)).label("unread"),
            ).where(Notification.user_id == uid)
        )
        counts = counts_result.one()
        total, unread_count = int(counts.total or 0), int(counts.unread or 0)

        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == uid)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return NotificationListResponse(
            items=[NotificationOut.model_validate(n) for n in items],
            unread_count=unread_count,
        )

    async def mark_read(self, db: AsyncSession, user_id: str, notification_id: uuid.UUID) -> None:
        uid = uuid.UUID(user_id)
        notif = await db.get(Notification, notification_id)
        if not notif or notif.user_id != uid:
            raise NotFoundError("通知不存在")
        notif.is_read = True
        await db.commit()

    async def mark_all_read(self, db: AsyncSession, user_id: str) -> None:
        uid = uuid.UUID(user_id)
        await db.execute(
            update(Notification)
            .where(Notification.user_id == uid, Notification.is_read == False)
            .values(is_read=True)
        )
        await db.commit()

    async def create(
        self,
        db: AsyncSession,
        user_id: str,
        content: str,
        notification_type: str,
        related_action: str | None = None,
        force_push: bool = False,
    ) -> Notification:
        """v0.34 P1-14 · 推送时段静默（22:00-06:00 不发 Expo push，但 in-app 仍写入）

        force_push=True 时强制推（保留给紧急通知用，目前不用）
        """
        uid = uuid.UUID(user_id)
        notif = Notification(
            user_id=uid,
            content=content,
            notification_type=notification_type,
            related_action=related_action,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)

        # 推送时段静默：22:00 - 06:00（北京时间）
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        # 用 UTC+8 算
        bj_now = _dt.now(_tz.utc) + _td(hours=8)
        hour = bj_now.hour
        in_quiet = (hour >= 22 or hour < 6)

        if in_quiet and not force_push:
            # 静默期：只入库不推 Expo，用户次日 06:00 后看到
            return notif

        # Attempt Expo push (non-blocking)
        user_row = await db.execute(select(User).where(User.id == uid))
        user = user_row.scalar_one_or_none()
        if user and user.expo_push_token:
            await _send_expo_push(user.expo_push_token, content)

        return notif

    # --- Organic push logic (called from Celery) ---

    async def generate_organic_notifications(self, db: AsyncSession, user_id: str) -> None:
        """Scans user state and creates relevant Agent-voiced notifications."""
        uid = uuid.UUID(user_id)
        now = datetime.now(timezone.utc)

        # Flashcard overdue check
        result = await db.execute(
            select(func.count()).select_from(Flashcard).where(
                Flashcard.user_id == uid,
                Flashcard.next_review_at <= now,
            )
        )
        overdue_count = result.scalar_one()
        if overdue_count >= 5:
            # Check if we sent this type recently (within 12h)
            recent = await db.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == uid,
                    Notification.notification_type == "flashcard_reminder",
                    Notification.created_at >= now - timedelta(hours=12),
                )
            )
            if recent.scalar_one() == 0:
                msg = self._flashcard_reminder_message(overdue_count)
                await self.create(db, user_id, msg, "flashcard_reminder", "/flashcards")

        # Streak warning: check if user hasn't checked in today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        checkin_result = await db.execute(
            select(func.count()).select_from(CheckIn).where(
                CheckIn.user_id == uid,
                CheckIn.created_at >= today_start,
            )
        )
        checked_in_today = checkin_result.scalar_one() > 0
        if not checked_in_today and now.hour >= 20:
            recent = await db.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == uid,
                    Notification.notification_type == "streak_warning",
                    Notification.created_at >= now - timedelta(hours=6),
                )
            )
            if recent.scalar_one() == 0:
                await self.create(
                    db, user_id,
                    "今天还没开始，明天是个容易划水的日子",
                    "streak_warning",
                    "/",
                )

        # Exam countdown reminders
        await self._check_exam_reminders(db, user_id, now)

    async def _check_exam_reminders(self, db: AsyncSession, user_id: str, now: datetime) -> None:
        uid = uuid.UUID(user_id)
        today = now.date()
        future_limit = today + timedelta(days=8)

        result = await db.execute(
            select(Exam).where(
                Exam.user_id == uid,
                Exam.exam_date > today,
                Exam.exam_date <= future_limit,
            )
        )
        exams = list(result.scalars().all())
        trigger_exams = [(e, (e.exam_date - today).days) for e in exams
                         if (e.exam_date - today).days in (1, 3, 7)]
        if not trigger_exams:
            return

        # Single batch query: all recent exam_reminder notifications in last 12h
        recent_result = await db.execute(
            select(Notification.content).where(
                Notification.user_id == uid,
                Notification.notification_type == "exam_reminder",
                Notification.created_at >= now - timedelta(hours=12),
            )
        )
        recently_notified: set[str] = {row[0] for row in recent_result.all()}

        for exam, days_left in trigger_exams:
            msg = self._exam_reminder_message(exam.name, days_left)
            # Skip if we already sent an identical message recently
            if msg not in recently_notified:
                await self.create(db, user_id, msg, "exam_reminder", "/exams")

    def _exam_reminder_message(self, name: str, days: int) -> str:
        if days == 1:
            return f"明天就是{name}了，今晚最后冲刺"
        elif days == 3:
            return f"距{name}还有3天，该收尾了"
        else:
            return f"距{name}还有一周，你知道的"

    def _flashcard_reminder_message(self, count: int) -> str:
        if count <= 10:
            return f"有{count}张卡我觉得你该看看了"
        elif count <= 30:
            return f"{count}张卡快忘了，今天有空吗"
        else:
            return f"积了{count}张卡了，找个时间清一清"
