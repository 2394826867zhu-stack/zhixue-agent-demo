"""F-10 用户 token 配额查询端点 GET /v1/profile/token-quota。

让前端在昂贵 LLM 调用前先查余量。必须与 enforcement（llm/client._check_quota）
读同一真相源：limit=DB 权威值（无则 DEFAULT），used=Redis quota:{uid}:used:{today}。
"""
from datetime import date

import pytest
from httpx import AsyncClient

from app.config import settings


async def _auth(client: AsyncClient, email: str) -> tuple[dict, str]:
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    me = await client.get("/v1/auth/me", headers=h)
    return h, me.json()["data"]["id"]


@pytest.mark.asyncio
async def test_reserve_rejects_when_over_limit(client: AsyncClient):
    """审计 L4-005：enforcement 拒绝路径。used >= limit 时 _reserve_quota 必须 raise
    QuotaExceededError（此前测套只验 GET /token-quota 读侧返回值，从不驱动拒绝分支）。"""
    from app.core.redis import get_redis
    from app.llm.client import llm_client, QuotaExceededError

    _, uid = await _auth(client, "quota_reject@zhiyao.ai")
    today = date.today().isoformat()
    key = f"quota:{uid}:used:{today}"
    global_key = f"quota:global:used:{today}"
    r = await get_redis()
    try:
        # used 超过默认 limit → 必须拒绝（拒绝路径不预扣，不改 key）
        await r.set(key, settings.DEFAULT_DAILY_TOKEN_LIMIT + 1)
        with pytest.raises(QuotaExceededError):
            await llm_client._reserve_quota(uid)
        # 控制对照：未超限 → 放行（不 raise），返回预扣量
        await r.set(key, 0)
        reserved = await llm_client._reserve_quota(uid)
        assert reserved == settings.QUOTA_RESERVE_ESTIMATE_TOKENS
    finally:
        await r.delete(key)
        await r.delete(global_key)


@pytest.mark.asyncio
async def test_token_quota_default_for_new_user(client: AsyncClient):
    h, _ = await _auth(client, "quota_default@zhiyao.ai")
    resp = await client.get("/v1/profile/token-quota", headers=h)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["daily_limit"] == settings.DEFAULT_DAILY_TOKEN_LIMIT
    assert data["used"] == 0, "新用户今日未消耗"
    assert data["remaining"] == settings.DEFAULT_DAILY_TOKEN_LIMIT
    assert data["is_default_limit"] is True
    assert data["date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_token_quota_reflects_redis_usage(client: AsyncClient):
    """验证 used 读的是 enforcement 真实 Redis 源，而非 hardcode。"""
    from app.core.redis import get_redis

    h, uid = await _auth(client, "quota_used@zhiyao.ai")
    today = date.today().isoformat()
    r = await get_redis()
    key = f"quota:{uid}:used:{today}"
    await r.set(key, 5000)
    try:
        resp = await client.get("/v1/profile/token-quota", headers=h)
        data = resp.json()["data"]
        assert data["used"] == 5000
        assert data["remaining"] == data["daily_limit"] - 5000
    finally:
        await r.delete(key)


@pytest.mark.asyncio
async def test_global_daily_circuit_breaker_rejects(client: AsyncClient, monkeypatch):
    """G2-2 全局熔断：单用户未超限但全局当日累计 token >= GLOBAL_DAILY_TOKEN_LIMIT
    时 _check_quota 必须拒绝（多用户并发击穿月预算的护栏）。"""
    from app.core.redis import get_redis
    from app.llm.client import llm_client, QuotaExceededError

    _, uid = await _auth(client, "quota_global@zhiyao.ai")
    today = date.today().isoformat()
    user_key = f"quota:{uid}:used:{today}"
    global_key = f"quota:global:used:{today}"
    r = await get_redis()
    # 全局限额压到 1000，单用户额度照常很大
    monkeypatch.setattr(settings, "GLOBAL_DAILY_TOKEN_LIMIT", 1000)
    try:
        await r.set(user_key, 0)  # 单用户未超限
        await r.set(global_key, 1000)  # 全局已达上限
        with pytest.raises(QuotaExceededError):
            await llm_client._reserve_quota(uid)
        # 控制对照：全局回落 → 放行
        await r.set(global_key, 0)
        await llm_client._reserve_quota(uid)
    finally:
        await r.delete(user_key)
        await r.delete(global_key)


@pytest.mark.asyncio
async def test_quota_fail_closed_when_redis_unavailable(client: AsyncClient, monkeypatch):
    """G2-3 fail-closed：配额系统（Redis）不可用时，默认保守拒绝；
    QUOTA_FAIL_OPEN=True 时才放行（运维可调）。"""
    from app.llm import client as client_mod
    from app.llm.client import llm_client, QuotaExceededError

    uid = "00000000-0000-0000-0000-000000000abc"

    async def _boom():
        raise RuntimeError("redis down")

    # 让 quota 检查里拿 redis 直接炸 → 模拟配额系统不可用
    monkeypatch.setattr(client_mod, "get_redis", _boom, raising=False)

    # 默认 fail-closed → 拒绝
    monkeypatch.setattr(settings, "QUOTA_FAIL_OPEN", False)
    with pytest.raises(QuotaExceededError):
        await llm_client._reserve_quota(uid)

    # flag 打开 → 放行（不 raise），返回 0（未预扣，无可退还）
    monkeypatch.setattr(settings, "QUOTA_FAIL_OPEN", True)
    assert await llm_client._reserve_quota(uid) == 0


@pytest.mark.asyncio
async def test_resolve_daily_limit_falls_back_to_db(db):
    """F-13：Redis 无 daily_limit 缓存时，enforcement 应回源 DB 权威值，而非退 DEFAULT。

    根因（审计 P1-3）：_check_quota 原本 Redis 未命中即用 DEFAULT，
    忽略 admin 在 DB 设的配额，与 /profile/token-quota（读 DB）不一致。
    """
    import uuid as _uuid

    from app.core.redis import get_redis
    from app.llm.client import llm_client
    from app.models.user_quota import UserQuota
    from tests.conftest import TestSessionLocal

    uid = _uuid.uuid4()
    db.add(UserQuota(user_id=uid, daily_token_limit=100))
    await db.commit()

    r = await get_redis()
    await r.delete(f"quota:{uid}:daily_limit")  # 确保 Redis 未命中
    try:
        limit = await llm_client._resolve_daily_limit(
            str(uid), session_factory=TestSessionLocal
        )
        assert limit == 100, "Redis 未命中应回源 DB 权威值 100，而非 DEFAULT"
    finally:
        await r.delete(f"quota:{uid}:daily_limit")


@pytest.mark.asyncio
async def test_reserve_serializes_concurrent_calls_no_bypass(client: AsyncClient):
    """P1-1 TOCTOU 回归：N 个并发预扣不再集体绕过。

    根因：旧 _check_quota 先 GET 比较、_record 事后才 INCRBY，N 并发都读到 used=0 集体通过。
    reserve 用 Lua 原子 check+INCRBY，第 N 个请求必然看到前 N-1 次预扣。
    limit=20000 / estimate=8000 → 仅前 3 个（used 0/8000/16000 均 <20000）放行，其余拒绝。
    """
    import asyncio

    from app.core.redis import get_redis
    from app.llm.client import llm_client, QuotaExceededError

    _, uid = await _auth(client, "quota_concurrent@zhiyao.ai")
    today = date.today().isoformat()
    user_key = f"quota:{uid}:used:{today}"
    global_key = f"quota:global:used:{today}"
    limit_key = f"quota:{uid}:daily_limit"
    r = await get_redis()
    est = settings.QUOTA_RESERVE_ESTIMATE_TOKENS
    limit = est * 2 + 1  # 恰好放行 3 个（used=0/est/2est < limit；3est >= limit 起拒）
    expected_pass = -(-limit // est)  # ceil(limit/est) = 3
    try:
        await r.set(user_key, 0)
        await r.set(global_key, 0)
        await r.set(limit_key, limit)  # _resolve_daily_limit 优先读 Redis 缓存

        results = await asyncio.gather(
            *[llm_client._reserve_quota(uid) for _ in range(10)],
            return_exceptions=True,
        )
        passed = [x for x in results if x == est]
        rejected = [x for x in results if isinstance(x, QuotaExceededError)]
        assert len(passed) == expected_pass, f"应恰好放行 {expected_pass} 个，实际 {len(passed)}"
        assert len(rejected) == 10 - expected_pass
        # 预扣真实落 Redis：used == 放行数 × estimate
        assert int(await r.get(user_key)) == expected_pass * est
    finally:
        await r.delete(user_key)
        await r.delete(global_key)
        await r.delete(limit_key)


@pytest.mark.asyncio
async def test_record_reconciles_reserved_to_actual(client: AsyncClient):
    """P1-1 reconcile：预扣 estimate 后，_record 按真实 usage 校正（delta=total-reserved）。
    预扣 8000 + 真实 1200 → 用户键净值 1200（而非 8000，更非 9200）。"""
    from app.core.redis import get_redis
    from app.llm.client import llm_client

    _, uid = await _auth(client, "quota_reconcile@zhiyao.ai")
    today = date.today().isoformat()
    user_key = f"quota:{uid}:used:{today}"
    global_key = f"quota:global:used:{today}"
    r = await get_redis()
    est = settings.QUOTA_RESERVE_ESTIMATE_TOKENS
    try:
        await r.delete(user_key)
        await r.delete(global_key)
        reserved = await llm_client._reserve_quota(uid)
        assert reserved == est
        assert int(await r.get(user_key)) == est, "预扣后应先记 estimate"
        # reconcile 到真实 1200 token
        await llm_client._record(
            uid, "deepseek-v4-flash", "test",
            {"prompt_tokens": 1000, "completion_tokens": 200}, reserved=reserved,
        )
        assert int(await r.get(user_key)) == 1200, "应校正为真实 total 1200"
        assert int(await r.get(global_key)) == 1200
    finally:
        await r.delete(user_key)
        await r.delete(global_key)


@pytest.mark.asyncio
async def test_refund_returns_reservation(client: AsyncClient):
    """P1-1 refund：LLM 调用失败时退还预扣，用户键/全局键回到原值。"""
    from app.core.redis import get_redis
    from app.llm.client import llm_client

    _, uid = await _auth(client, "quota_refund@zhiyao.ai")
    today = date.today().isoformat()
    user_key = f"quota:{uid}:used:{today}"
    global_key = f"quota:global:used:{today}"
    r = await get_redis()
    est = settings.QUOTA_RESERVE_ESTIMATE_TOKENS
    try:
        await r.delete(user_key)
        await r.delete(global_key)
        reserved = await llm_client._reserve_quota(uid)
        assert int(await r.get(user_key)) == est
        await llm_client._refund_quota(uid, reserved)
        assert int(await r.get(user_key)) == 0, "退还后用户键应回零"
        assert int(await r.get(global_key)) == 0, "退还后全局键应回零"
    finally:
        await r.delete(user_key)
        await r.delete(global_key)
