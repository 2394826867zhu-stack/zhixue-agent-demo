"""G2-4 可观测 · Sentry 外部错误上报（审计 P0）。

设计铁律：**仅 `SENTRY_DSN` 非空才 init**。无 DSN 时 `init_sentry()` 直接返回，
不 import 任何会失败的东西、不上报、不触发网络——本地开发零依赖、零副作用。

一处 init 覆盖 FastAPI（web 进程）+ Celery（worker 进程）。两个进程入口分别
调用 `init_sentry()`（main.py lifespan / celery_app 加载时），CeleryIntegration
自动捕获任务异常；FastAPI 未捕获异常经全局 handler 里 `capture_exception` 补报。
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def init_sentry() -> bool:
    """按需初始化 Sentry。返回 True=已 init，False=跳过（无 DSN）。

    幂等：多进程/多次调用安全（已 init 直接返回 True）。
    """
    global _initialized
    if _initialized:
        return True
    if not settings.SENTRY_DSN:
        # 无 DSN → 静默跳过，本地开发零依赖
        return False

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            CeleryIntegration(),
        ],
        # 不发 PII（请求体/headers 可能含 token / 用户输入），与 PII mask 策略一致
        send_default_pii=False,
    )
    _initialized = True
    logger.info("Sentry 已初始化 (env=%s)", settings.APP_ENV)
    return True


def capture_exception(exc: BaseException) -> None:
    """上报异常到 Sentry（无 DSN 时 no-op，绝不抛错阻断主流程）。"""
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover - 上报失败绝不影响主流程
        logger.exception("Sentry capture_exception 失败")


def capture_message(message: str, level: str = "error") -> None:
    """主动告警消息到 Sentry（无 DSN 时 no-op）。用于 DLQ 等无异常对象的告警。"""
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except Exception:  # pragma: no cover
        logger.exception("Sentry capture_message 失败")
