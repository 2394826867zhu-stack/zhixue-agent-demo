import logging
import asyncio
from datetime import date
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.task_tasks.generate_daily_tasks_all_users")
def generate_daily_tasks_all_users():
    """Celery beat: generate today's tasks for all active users at 00:05."""
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    asyncio.run(_generate_all())


async def _generate_all():
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.services.task_service import task_service
    from app.core.redis import get_redis

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User.id))
        user_ids = [str(row[0]) for row in result]

    redis = await get_redis()
    today = str(date.today())

    for user_id in user_ids:
        # Redis SETNX guard: only one worker generates tasks per user per day.
        # pg_advisory_xact_lock inside generate_today handles the DB-level race;
        # this Redis lock prevents the expensive AI call from running twice at all.
        lock_key = f"daily_task_lock:{user_id}:{today}"
        acquired = await redis.set(lock_key, "1", nx=True, ex=86400)
        if not acquired:
            logger.info(f"Daily tasks for user {user_id} already generated today, skipping")
            continue
        try:
            async with AsyncSessionLocal() as db:
                await task_service.generate_today(db, user_id)
                logger.info(f"Generated daily tasks for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to generate tasks for user {user_id}: {e}")
            # Release lock so it can be retried later in case of transient failure
            await redis.delete(lock_key)
