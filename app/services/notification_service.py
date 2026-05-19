import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.flashcard import Flashcard
from app.models.checkin import CheckIn
from app.models.exam import Exam
from app.schemas.notification import NotificationOut, NotificationListResponse
from app.core.exceptions import NotFoundError


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
        total_result = await db.execute(
            select(func.count()).select_from(Notification).where(Notification.user_id == uid)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == uid)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        unread_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == uid, Notification.is_read == False
            )
        )
        unread_count = unread_result.scalar_one()

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
    ) -> Notification:
        notif = Notification(
            user_id=uuid.UUID(user_id),
            content=content,
            notification_type=notification_type,
            related_action=related_action,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
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
        for exam in exams:
            days_left = (exam.exam_date - today).days
            if days_left not in (1, 3, 7):
                continue
            # Don't send duplicate for same exam + days_left within 12h
            recent = await db.execute(
                select(func.count()).select_from(Notification).where(
                    Notification.user_id == uid,
                    Notification.notification_type == "exam_reminder",
                    Notification.content.contains(exam.name),
                    Notification.created_at >= now - timedelta(hours=12),
                )
            )
            if recent.scalar_one() == 0:
                msg = self._exam_reminder_message(exam.name, days_left)
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
