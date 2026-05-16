from celery import Celery
from app.config import settings

celery_app = Celery(
    "zhiyao",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.note_tasks", "app.tasks.task_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        # 每天凌晨0:05生成每日任务
        "generate-daily-tasks": {
            "task": "app.tasks.task_tasks.generate_daily_tasks_all_users",
            "schedule": 300.0,  # dev: every 5min; prod: crontab(hour=0, minute=5)
        },
    },
)
