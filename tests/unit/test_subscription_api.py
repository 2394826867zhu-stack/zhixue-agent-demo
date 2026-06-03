import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_subscription_status_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/subscription/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_webhook_rejects_missing_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/subscription/webhook", json={"event": {}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret():
    from app.config import settings

    with patch.object(settings, "REVENUECAT_WEBHOOK_SECRET", "real-secret"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/subscription/webhook",
                json={"event": {"id": "x", "type": "INITIAL_PURCHASE", "app_user_id": "y"}},
                headers={"Authorization": "Bearer wrong-secret"},
            )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_fail_closed_when_secret_unset():
    # 审计 L5：未配置 secret（dev 默认空）时必须 fail-closed（403），
    # 不得接受带任意 Authorization 的伪造请求（否则攻击者可改任意用户为 Pro）。
    from app.config import settings

    with patch.object(settings, "REVENUECAT_WEBHOOK_SECRET", ""):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/subscription/webhook",
                json={"event": {"id": "x", "type": "INITIAL_PURCHASE", "app_user_id": "y"}},
                headers={"Authorization": "Bearer anything"},
            )
    assert resp.status_code == 403
