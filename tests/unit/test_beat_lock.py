"""P1-10 · beat 单跑分布式锁（beat_singleflight）单元测试。

锁住整任务，同一时间窗只放行一次；Redis 不可用 fail-open；任务体异常释放锁。
"""
import pytest

from app.tasks.beat_lock import beat_singleflight


@pytest.mark.asyncio
async def test_same_window_runs_once_then_skips():
    from app.core.redis import get_redis

    r = await get_redis()
    name, window = "test_task", "2026-06-23:14"
    key = f"beat_lock:{name}:{window}"
    await r.delete(key)
    try:
        # 第一次拿到锁
        async with beat_singleflight(name, window, ttl_seconds=60) as go1:
            assert go1 is True
        # 同窗第二次被占 → 跳过
        async with beat_singleflight(name, window, ttl_seconds=60) as go2:
            assert go2 is False
        # 不同窗 → 放行
        async with beat_singleflight(name, "2026-06-23:15", ttl_seconds=60) as go3:
            assert go3 is True
    finally:
        await r.delete(key)
        await r.delete(f"beat_lock:{name}:2026-06-23:15")


@pytest.mark.asyncio
async def test_exception_releases_lock_for_retry():
    """任务体抛异常 → 释放锁，重试可再拿。"""
    from app.core.redis import get_redis

    r = await get_redis()
    name, window = "test_task_exc", "2026-06-23:14"
    key = f"beat_lock:{name}:{window}"
    await r.delete(key)
    try:
        with pytest.raises(RuntimeError):
            async with beat_singleflight(name, window, ttl_seconds=60) as go:
                assert go is True
                raise RuntimeError("boom")
        # 锁已释放 → 重试能再拿到
        assert await r.get(key) is None
        async with beat_singleflight(name, window, ttl_seconds=60) as go2:
            assert go2 is True
    finally:
        await r.delete(key)


@pytest.mark.asyncio
async def test_redis_unavailable_fail_open(monkeypatch):
    """Redis 不可用 → fail-open 放行（可用性优先，任务内层有幂等/去重兜底）。"""
    import app.tasks.beat_lock as mod

    async def _boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(mod, "get_redis", _boom)
    async with beat_singleflight("whatever", "win", ttl_seconds=60) as go:
        assert go is True
