"""G5-3 · 反馈/客服到达 Sentry 通知（告警可见）端到端测试。

落库后触发 observability.capture_message（无 DSN 时本身 no-op，这里 mock 断言被调），
告警失败不阻断主流程。
"""
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str) -> str:
    resp = await client.post("/v1/auth/register", json={"email": email, "password": "password123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_feedback_triggers_arrival_notification(client: AsyncClient, monkeypatch):
    import app.services.feedback_service as fb_svc

    calls = []
    monkeypatch.setattr(
        fb_svc, "capture_message", lambda msg, level="error": calls.append((msg, level))
    )

    token = await _register(client, "fb_notify@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/v1/feedback",
        headers=H,
        json={"category": "bug", "content": "点提交报错"},
    )
    assert resp.status_code == 200, resp.text

    assert len(calls) == 1, "落库后应触发一次到达通知"
    msg, level = calls[0]
    assert "[Feedback]" in msg
    assert "bug" in msg
    assert level == "info"


@pytest.mark.asyncio
async def test_support_thread_triggers_arrival_notification(client: AsyncClient, monkeypatch):
    import app.services.support_service as sup_svc

    calls = []
    monkeypatch.setattr(
        sup_svc, "capture_message", lambda msg, level="error": calls.append((msg, level))
    )

    token = await _register(client, "sup_notify@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/v1/support/threads",
        headers=H,
        json={"subject": "无法登录", "message": "一直转圈"},
    )
    assert resp.status_code == 200, resp.text

    assert len(calls) == 1, "新客服会话应触发一次到达通知"
    msg, level = calls[0]
    assert "[Support]" in msg
    assert level == "info"


@pytest.mark.asyncio
async def test_arrival_notification_failure_does_not_break_flow(client: AsyncClient, monkeypatch):
    """告警抛错不应阻断反馈落库主流程。"""
    import app.services.feedback_service as fb_svc

    def boom(msg, level="error"):
        raise RuntimeError("sentry down")

    monkeypatch.setattr(fb_svc, "capture_message", boom)

    token = await _register(client, "fb_resilient@zhiyao.ai")
    H = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/v1/feedback",
        headers=H,
        json={"category": "other", "content": "随便说点"},
    )
    assert resp.status_code == 200, resp.text
    # 反馈仍能查回
    resp = await client.get("/v1/feedback", headers=H)
    assert len(resp.json()["data"]) == 1
