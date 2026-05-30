"""F-11 · Celery 任务失败 → 死信队列 + 管理员告警。

`task_failure` 信号在任务**最终失败**（重试耗尽后）触发，一处全局覆盖所有任务，
无需逐个任务改 on_failure。失败任务不再静默丢失。
"""
import asyncio
import logging

from celery.signals import task_failure

logger = logging.getLogger(__name__)


@task_failure.connect
def handle_task_failure(
    sender=None, task_id=None, exception=None, args=None, kwargs=None, einfo=None, **kw
):
    task_name = getattr(sender, "name", "unknown")
    error = str(exception) if exception else "unknown error"
    tb = str(einfo) if einfo else None
    retries = getattr(getattr(sender, "request", None), "retries", 0) or 0

    # 管理员告警：ERROR 级日志（运维监控/Sentry 可订阅）。
    # 如需即时推送，可在此读 settings.ADMIN_ALERT_WEBHOOK 发送，缺省走日志。
    logger.error(
        "[DLQ] Celery 任务最终失败 task=%s id=%s retries=%s error=%s",
        task_name, task_id, retries, error,
    )

    # 持久化到死信队列表（管理员可查 / 后续可重放）
    try:
        from app.core.database import async_session_factory
        from app.services.dead_letter_service import dead_letter_service

        async def _record():
            async with async_session_factory() as db:
                await dead_letter_service.record_failure(
                    db,
                    task_name=task_name,
                    task_id=task_id,
                    args=list(args or []),
                    kwargs=dict(kwargs or {}),
                    error=error,
                    traceback=tb,
                    retries=retries,
                )

        asyncio.run(_record())
    except Exception as e:
        logger.error("[DLQ] 写入死信队列失败: %s", e)
