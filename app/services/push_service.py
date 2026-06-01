"""Expo Push 发送服务 (C-18)

Returns None on success, error_type string on failure.
Callers handle DeviceNotRegistered by clearing the token.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

_EXPO_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(token: str, body: str) -> str | None:
    """Fire an Expo push notification.

    Returns None on success, or an error_type string:
      - "DeviceNotRegistered": token is stale; caller should clear it
      - "network_error": transient; safe to ignore
      - other string: Expo error details
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _EXPO_URL,
                json={"to": token, "title": "知曜", "body": body, "sound": "default"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
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
