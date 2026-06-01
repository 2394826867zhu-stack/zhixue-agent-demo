import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_push_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"status": "ok", "id": "abc123"}]}

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[xxx]", "测试内容")

    assert result is None  # None = success


@pytest.mark.asyncio
async def test_send_push_device_not_registered():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"status": "error", "message": "...", "details": {"error": "DeviceNotRegistered"}}]
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[stale]", "内容")

    assert result == "DeviceNotRegistered"


@pytest.mark.asyncio
async def test_send_push_network_error():
    import httpx
    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[xxx]", "内容")

    assert result == "network_error"
