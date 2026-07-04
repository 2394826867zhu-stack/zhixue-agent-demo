"""Expo Push 发送服务 (C-18)

Returns None on success, error_type string on failure.
Callers handle DeviceNotRegistered by clearing the token.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

_EXPO_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(token: str, body: str, data: dict | None = None) -> str | None:
    """Fire an Expo push notification.

    data: 附加负载（notification_type / related_action），客户端点击推送时
          据此深链到对应内容屏（A·P2-2）；None 则不带。

    Returns None on success, or an error_type string:
      - "DeviceNotRegistered": token is stale; caller should clear it
      - "network_error": transient; safe to ignore
      - other string: Expo error details
    """
    payload: dict = {"to": token, "title": "知曜", "body": body, "sound": "default"}
    if data:
        payload["data"] = data
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _EXPO_URL,
                json=payload,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            tickets = resp.json().get("data", [])
            ticket = tickets[0] if tickets else {}
            if ticket.get("status") == "error":
                error_type = ticket.get("details", {}).get("error") or "unknown"
                logger.debug(f"Expo push error {error_type} for token …{token[-8:]}")
                return error_type
            return None
    except Exception as exc:
        logger.debug(f"Expo push network error: {exc}")
        return "network_error"
