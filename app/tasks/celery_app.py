from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "zhiyao",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.note_tasks", "app.tasks.task_tasks", "app.tasks.notification_tasks"],
)

# dev: every 5 min (so daily-task logic runs during demos); prod: once at 00:05
_daily_task_schedule = (
    300.0
    if settings.APP_ENV == "development"
    else crontab(hour=0, minute=5)
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "generate-daily-tasks": {
            "task": "app.tasks.task_tasks.generate_daily_tasks_all_users",
            "schedule": _daily_task_schedule,
        },
        "recover-stuck-notes": {
            "task": "app.tasks.note_tasks.recover_stuck_notes",
            "schedule": 1800.0,
        },
        # organic push: 08:00 and 20:00 daily
        "push-organic-notifications-morning": {
            "task": "app.tasks.notification_tasks.push_organic_notifications",
            "schedule": crontab(hour=8, minute=0) if settings.APP_ENV != "development" else 3600.0,
        },
        "push-organic-notifications-evening": {
            "task": "app.tasks.notification_tasks.push_organic_notifications",
            "schedule": crontab(hour=20, minute=0) if settings.APP_ENV != "development" else 7200.0,
        },
    },
)
