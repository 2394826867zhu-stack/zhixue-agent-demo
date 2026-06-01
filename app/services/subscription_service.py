"""E-01~E-03 · Subscription tier service.

plan_type values: "free" | "pro" | "edu"
- "free"  : default, no Pro features
- "pro"   : active paid subscription (check plan_expires_at)
- "edu"   : manually granted by admin, no expiry
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# RevenueCat event types that grant or revoke Pro access
_GRANT_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE", "UNCANCELLATION"}
_REVOKE_EVENTS = {"EXPIRATION"}
# CANCELLATION does NOT revoke — user keeps access until expires_at


def is_pro(user) -> bool:
    """Return True if user currently has active Pro (or Edu) access."""
    if user.plan_type == "edu":
        return True
    if user.plan_type == "pro":
        if user.plan_expires_at is None:
            return True  # lifetime / no-expiry grant
        return user.plan_expires_at > datetime.now(timezone.utc)
    return False


def get_status(user) -> dict[str, Any]:
    """Return subscription status dict for the /status endpoint."""
    pro = is_pro(user)
    days_remaining: int | None = None
    if user.plan_type == "pro" and user.plan_expires_at is not None:
        delta = user.plan_expires_at - datetime.now(timezone.utc)
        days_remaining = max(0, delta.days)

    return {
        "plan_type": user.plan_type,
        "is_pro": pro,
        "plan_expires_at": user.plan_expires_at,
        "days_remaining": days_remaining,
        "features": {
            "unlimited_agent": pro,
            "advanced_reports": pro,
            "knowledge_base_upload": pro,
        },
    }


def verify_webhook_auth(authorization_header: str | None, secret: str) -> bool:
    """Validate RevenueCat webhook Authorization header.

    RevenueCat sends: Authorization: Bearer <secret>
    Configure the secret in the RevenueCat dashboard → Webhooks → Authorization header.
    """
    if not authorization_header or not secret:
        return False
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == secret


async def apply_revenuecat_event(db, payload: dict) -> None:
    """Parse a RevenueCat webhook event and update the user's subscription tier.

    Idempotent: duplicate events (same revenuecat_event_id) are silently ignored.
    """
    from sqlalchemy import select
    from app.models.user import User
    from app.models.subscription_event import SubscriptionEvent

    event = payload.get("event", {})
    event_id = event.get("id", "")
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id")
    expiration_at_ms = event.get("expiration_at_ms")

    if not event_id or not event_type or not app_user_id:
        logger.warning("RevenueCat webhook missing required fields: %s", payload)
        return

    # Idempotency check
    existing = await db.execute(
        select(SubscriptionEvent).where(SubscriptionEvent.revenuecat_event_id == event_id)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Duplicate RevenueCat event %s — skipped", event_id)
        return

    # Resolve expires_at
    expires_at: datetime | None = None
    if expiration_at_ms is not None:
        expires_at = datetime.fromtimestamp(expiration_at_ms / 1000, tz=timezone.utc)

    # Resolve user by app_user_id (we set this to user UUID in the mobile SDK)
    import uuid as _uuid
    try:
        uid = _uuid.UUID(app_user_id)
    except ValueError:
        logger.warning("RevenueCat app_user_id is not a UUID: %s", app_user_id)
        uid = None

    user = None
    if uid is not None:
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()

    # Update user plan
    if user is not None:
        if event_type in _GRANT_EVENTS:
            user.plan_type = "pro"
            user.plan_expires_at = expires_at
        elif event_type in _REVOKE_EVENTS:
            user.plan_type = "free"
            user.plan_expires_at = None

    # Record audit event
    se = SubscriptionEvent(
        user_id=user.id if user else None,
        revenuecat_event_id=event_id,
        event_type=event_type,
        product_id=product_id,
        expires_at=expires_at,
        raw_payload=payload,
    )
    db.add(se)
    await db.commit()
    logger.info("Processed RevenueCat event %s (%s) for user %s", event_id, event_type, app_user_id)
