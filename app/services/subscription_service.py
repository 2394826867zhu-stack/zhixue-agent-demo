"""E-01~E-03 · Subscription tier service.

plan_type values: "free" | "pro" | "edu"
- "free"  : default, no Pro features
- "pro"   : active paid subscription (check plan_expires_at)
- "edu"   : manually granted by admin, no expiry
"""
from __future__ import annotations

import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.subscription_event import SubscriptionEvent
from app.models.user import User

logger = logging.getLogger(__name__)

# E-04 · 免费试用天数
TRIAL_DAYS = 7

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


def is_on_trial(user) -> bool:
    """当前 Pro 是否来自免费试用（trial_ends_at 在未来且仍是 pro）。"""
    return (
        user.plan_type == "pro"
        and getattr(user, "trial_ends_at", None) is not None
        and user.trial_ends_at > datetime.now(timezone.utc)
    )


def trial_available(user) -> bool:
    """是否还能领取免费试用：未用过 且 当前是 free。"""
    return (not getattr(user, "trial_used", False)) and user.plan_type == "free"


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
        "is_trial": is_on_trial(user),
        "trial_available": trial_available(user),
        "features": {
            "unlimited_agent": pro,
            "advanced_reports": pro,
            "knowledge_base_upload": pro,
        },
    }


async def start_trial(db, user: User) -> dict[str, Any]:
    """E-04 · 启动 7 天 Pro 免费试用（每人仅一次）。

    守卫：已是 Pro/Edu → 拒绝；已用过试用 → 拒绝。
    成功：plan_type=pro + plan_expires_at/trial_ends_at = now+7d + trial_used=True，
    并写一条 TRIAL_START 审计事件。
    """
    if user.plan_type in ("pro", "edu") and is_pro(user):
        raise AppError(4003, "你已经是 Pro 会员了，无需试用", 400)
    if getattr(user, "trial_used", False):
        raise AppError(4003, "你已经使用过免费试用啦", 400)

    now = datetime.now(timezone.utc)
    ends = now + timedelta(days=TRIAL_DAYS)
    user.plan_type = "pro"
    user.plan_expires_at = ends
    user.trial_ends_at = ends
    user.trial_used = True

    db.add(SubscriptionEvent(
        user_id=user.id,
        revenuecat_event_id=f"trial:{user.id}",  # 唯一约束兜底防重复领取
        event_type="TRIAL_START",
        product_id=None,
        expires_at=ends,
        raw_payload={"source": "in_app_trial", "trial_days": TRIAL_DAYS},
    ))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(user)
    return get_status(user)


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
    return hmac.compare_digest(parts[1], secret)


async def apply_revenuecat_event(db, payload: dict) -> None:
    """Parse a RevenueCat webhook event and update the user's subscription tier.

    Idempotent: duplicate events (same revenuecat_event_id) are silently ignored.
    """
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
    try:
        uid = uuid.UUID(app_user_id)
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
            user.trial_ends_at = None  # 付费订阅取代试用，状态不再显示「试用中」
        elif event_type in _REVOKE_EVENTS:
            user.plan_type = "free"
            user.plan_expires_at = None
        else:
            logger.debug("Unrecognized event_type %s — no plan change applied", event_type)

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
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    logger.info("Processed RevenueCat event %s (%s) for user %s", event_id, event_type, app_user_id)
