"""P1-7 · 结构化日志 + request_id 关联。

生产输出 JSON 行（便于 ELK/Loki/CloudWatch 聚合 + 按 request_id 串起一次请求的全部日志），
开发输出人读 plain。request_id 经 ContextVar 注入：中间件每请求生成（或透传上游
X-Request-ID），同请求内所有日志自动带上，无需逐处传参。
"""
import logging
import logging.config
import sys
import uuid
from contextvars import ContextVar

from pythonjsonlogger import jsonlogger

from app.config import settings

# 当前请求的关联 ID（中间件设置；请求外为 None，如启动/Celery）
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def get_request_id() -> str | None:
    return request_id_var.get()


class RequestIdJsonFormatter(jsonlogger.JsonFormatter):
    """JSON 行格式，注入 level/logger/request_id 标准字段。"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        rid = request_id_var.get()
        if rid:
            log_record["request_id"] = rid


def _resolve_format() -> str:
    """空 = 按环境自动（生产 json / 开发 plain）；显式值覆盖。"""
    if settings.LOG_FORMAT:
        return settings.LOG_FORMAT
    return "json" if settings.APP_ENV == "production" else "plain"


def configure_logging() -> None:
    """统一日志配置（dictConfig）。幂等：可重复调用。覆盖 root + uvicorn 三 logger，
    避免 uvicorn 默认 handler 与本配置双写。"""
    fmt = _resolve_format()
    formatter = "json" if fmt == "json" else "plain"
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
            "json": {
                "()": "app.core.logging_setup.RequestIdJsonFormatter",
                # 字段经 add_fields 注入；format 仅声明取哪些基础字段
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
                "stream": sys.stdout,
            },
        },
        "root": {"handlers": ["default"], "level": settings.LOG_LEVEL},
        "loggers": {
            name: {"handlers": ["default"], "level": settings.LOG_LEVEL, "propagate": False}
            for name in ("uvicorn", "uvicorn.access", "uvicorn.error")
        },
    })
