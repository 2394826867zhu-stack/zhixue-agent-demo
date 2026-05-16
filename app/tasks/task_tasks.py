import logging
import asyncio
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.task_tasks.generate_daily_tasks_all_users")
def generate_daily_tasks_all_users():
    """Celery beat: generate today's tasks for all active users at 00:05."""
    asyncio.run(_generate_all())


async def _generate_all():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.services.task_service import task_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User.id))
        user_ids = [str(row[0]) for row in result]

    for user_id in user_ids:
        try:
            async with AsyncSessionLocal() as db:
                await task_service.generate_today(db, user_id)
                logger.info(f"Generated daily tasks for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to generate tasks for user {user_id}: {e}")
