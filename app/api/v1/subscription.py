import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.exceptions import AppError
from app.config import settings
from app.models.user import User
from app.schemas.subscription import SubscriptionStatusOut, SubscriptionFeatures
from app.services.subscription_service import get_status, verify_webhook_auth, apply_revenuecat_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["订阅"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/status", summary="当前订阅状态")
async def subscription_status(
    user: User = Depends(get_current_user),
):
    data = get_status(user)
    return ok(
        SubscriptionStatusOut(
            plan_type=data["plan_type"],
            is_pro=data["is_pro"],
            plan_expires_at=data["plan_expires_at"],
            days_remaining=data["days_remaining"],
            features=SubscriptionFeatures(**data["features"]),
        )
    )


@router.post("/webhook", summary="RevenueCat webhook（服务端专用）")
async def revenuecat_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive RevenueCat subscription lifecycle events.

    Authentication: RevenueCat sends `Authorization: Bearer <secret>`.
    Configure REVENUECAT_WEBHOOK_SECRET in .env to match the secret set in the
    RevenueCat dashboard → Project Settings → Webhooks → Authorization header.

    If REVENUECAT_WEBHOOK_SECRET is empty (dev default), the endpoint accepts all
    requests that include an Authorization header, and only logs — safe for local testing.
    """
    auth_header = request.headers.get("Authorization")
    secret = settings.REVENUECAT_WEBHOOK_SECRET

    if not auth_header:
        raise AppError(4010, "Webhook 签名无效", 401)
    if secret and not verify_webhook_auth(auth_header, secret):
        raise AppError(4010, "Webhook 签名无效", 401)

    try:
        payload = await request.json()
    except Exception:
        raise AppError(4000, "请求体不是有效 JSON", 400)

    await apply_revenuecat_event(db, payload)
    return ok(None)
