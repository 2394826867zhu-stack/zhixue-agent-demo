from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "zhiyao",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.note_tasks",
        "app.tasks.task_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.embedding_tasks",  # v0.28 RAG
        "app.tasks.memory_tasks",     # v0.29 Memory
        "app.tasks.first_review_tasks",  # v0.33 P0-1 · 24h 首次复习推送
        "app.tasks.weekly_reflection_tasks",  # v0.33 P0-3 · 周复盘自动生成
        "app.tasks.dead_letter",  # F-11 · task_failure → 死信队列 + 告警
        "app.tasks.learning_kernel_tasks",  # 学习内核 P0-7 · 掌握度校准监控
        "app.tasks.review_due_tasks",    # C-17/C-19 · FSRS 到期复习推送
        "app.tasks.checkin_reminder_tasks",  # C-20 · 每日打卡提醒
    ],
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
        # v0.29 Memory · 行为信号扫描
        "scan-inactive-users": {
            "task": "app.tasks.memory_tasks.scan_inactive_users",
            "schedule": crontab(hour=22, minute=30) if settings.APP_ENV != "development" else 3600.0,
        },
        "scan-upcoming-exams": {
            "task": "app.tasks.memory_tasks.scan_upcoming_exams",
            "schedule": crontab(hour=9, minute=0) if settings.APP_ENV != "development" else 7200.0,
        },
        "cleanup-old-episodes": {
            "task": "app.tasks.memory_tasks.cleanup_old_episodes",
            "schedule": crontab(hour=3, minute=0) if settings.APP_ENV != "development" else 86400.0,
        },
        # v0.33 P0-1 · 24h 首次复习推送（每小时扫一次）
        "scan-first-review-due": {
            "task": "app.tasks.first_review_tasks.scan_first_review_due",
            "schedule": crontab(minute=15) if settings.APP_ENV != "development" else 3600.0,
        },
        # v0.33 P0-3 · 周复盘自动（每周日 20:00）
        "generate-weekly-reflection": {
            "task": "app.tasks.weekly_reflection_tasks.generate_all_users",
            "schedule": crontab(day_of_week="sun", hour=20, minute=0)
                        if settings.APP_ENV != "development" else 86400.0,
        },
        # v0.34 P1-11 · 6h 软提醒（每小时扫一次）
        "scan-focus-overload": {
            "task": "app.tasks.focus_overload_tasks.scan_overload",
            "schedule": crontab(minute=45) if settings.APP_ENV != "development" else 3600.0,
        },
        # 学习内核 P0-7 · 掌握度校准监控（ECE>0.2 告警）
        "mastery-calibration-monitor": {
            "task": "app.tasks.learning_kernel_tasks.mastery_calibration_check",
            "schedule": 600.0 if settings.APP_ENV == "development" else crontab(hour=2, minute=0),
        },
        # C-17/C-19 · FSRS 复习到期推送（每小时 :30 分）
        "scan-review-due": {
            "task": "app.tasks.review_due_tasks.scan_review_due",
            "schedule": crontab(minute=30) if settings.APP_ENV != "development" else 3600.0,
        },
        # C-20 · 每日打卡提醒（每小时 :50 分）
        "scan-checkin-reminder": {
            "task": "app.tasks.checkin_reminder_tasks.scan_checkin_reminder",
            "schedule": crontab(minute=50) if settings.APP_ENV != "development" else 3600.0,
        },
    },
)
