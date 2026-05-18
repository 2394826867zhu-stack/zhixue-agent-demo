import asyncio
from celery import shared_task
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.user import User
from app.services.notification_service import NotificationService


@shared_task(name="app.tasks.notification_tasks.push_organic_notifications")
def push_organic_notifications() -> dict:
    """Scans all active users and creates organic Agent notifications as needed."""
    return asyncio.run(_push_all())


async def _push_all() -> dict:
    svc = NotificationService()
    pushed = 0
    errors = 0

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.onboarding_completed == True))
        users = list(result.scalars().all())

    for user in users:
        try:
            async with async_session_factory() as db:
                await svc.generate_organic_notifications(db, str(user.id))
                pushed += 1
        except Exception:
            errors += 1

    return {"pushed": pushed, "errors": errors}
