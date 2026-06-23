"""P1-10 · beat 单跑分布式锁。

beat 周期任务可能被重复执行（acks_late 重投 / 误配多 beat / worker 抖动），
昂贵的"全体用户扫描 + LLM"重复跑既浪费成本又可能重复推送。用 Redis SETNX 在
任务入口加分布式锁：同一时间窗只跑一次。范例见 app/tasks/task_tasks.py（per-user 锁），
本模块是整任务（per-window）锁。
"""
import logging
from contextlib import asynccontextmanager

from app.core.redis import get_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def beat_singleflight(name: str, window: str, ttl_seconds: int):
    """yields True=拿到锁应执行；False=本窗已被占应跳过。

    name=任务标识，window=时间窗（如 `日期:小时` / ISO 周，决定锁粒度）。
    成功保留锁到 TTL（去重同窗重投）；未捕获异常释放锁 + 上抛（让 Celery 重试可再跑，
    不永久吞掉本窗执行）。

    Redis 不可用时 **fail-open**（yield True）——这些是带内层幂等/去重兜底的通知扫描
    （8h/23h 去重、周复盘 upsert），可用性优先；不该因锁基础设施抖动而静默漏推。
    （与成本命门 LLM 配额的 fail-closed 取向不同，那里宁拒不击穿。）
    """
    key = f"beat_lock:{name}:{window}"
    redis = None
    try:
        redis = await get_redis()
        acquired = await redis.set(key, "1", nx=True, ex=ttl_seconds)
    except Exception as exc:
        logger.warning(f"beat_singleflight redis unavailable for {key}, fail-open: {exc}")
        yield True
        return
    if not acquired:
        logger.info(f"beat_singleflight {key} held — skipping duplicate run")
        yield False
        return
    try:
        yield True
    except Exception:
        try:
            await redis.delete(key)  # 失败释放，允许重试再跑
        except Exception:
            pass
        raise
