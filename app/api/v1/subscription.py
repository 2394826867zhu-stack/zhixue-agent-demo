import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.exceptions import AppError
from app.config import settings
from app.models.user import User
from app.schemas.subscription import SubscriptionStatusOut, SubscriptionFeatures
from app.schemas.envelope import Envelope
from app.services.subscription_service import (
    get_status, verify_webhook_auth, apply_revenuecat_event, start_trial,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["订阅"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


def _to_out(data: dict) -> SubscriptionStatusOut:
    return SubscriptionStatusOut(
        plan_type=data["plan_type"],
        is_pro=data["is_pro"],
        plan_expires_at=data["plan_expires_at"],
        days_remaining=data["days_remaining"],
        is_trial=data.get("is_trial", False),
        trial_available=data.get("trial_available", False),
        features=SubscriptionFeatures(**data["features"]),
    )


@router.get("/status", summary="当前订阅状态", response_model=Envelope[SubscriptionStatusOut])
async def subscription_status(
    user: User = Depends(get_current_user),
):
    return ok(_to_out(get_status(user)))


@router.post("/trial", summary="启动 7 天 Pro 免费试用（每人仅一次）", response_model=Envelope[SubscriptionStatusOut])
async def start_pro_trial(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await start_trial(db, user)
    return ok(_to_out(data))


@router.post("/webhook", summary="RevenueCat webhook（服务端专用）", response_model=Envelope[None])
async def revenuecat_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive RevenueCat subscription lifecycle events.

    Authentication: RevenueCat sends `Authorization: Bearer <secret>`.
    Configure REVENUECAT_WEBHOOK_SECRET in .env to match the secret set in the
    RevenueCat dashboard → Project Settings → Webhooks → Authorization header.

    Fail-closed（审计 L5）：若 REVENUECAT_WEBHOOK_SECRET 未配置（空），端点拒绝处理任何
    请求（403），而非接受带任意 Authorization header 的请求——否则攻击者可在 dev 默认空 secret
    下伪造 RevenueCat 事件把任意用户改成 Pro。本地测试请显式配置一个 dev secret。
    """
    auth_header = request.headers.get("Authorization")
    secret = settings.REVENUECAT_WEBHOOK_SECRET

    if not auth_header:
        raise AppError(4010, "Webhook 签名无效", 401)
    if not secret:
        # 未配置 secret → fail-closed 拒绝（绝不 accept-all）
        raise AppError(4030, "Webhook 未配置密钥，拒绝处理", 403)
    if not verify_webhook_auth(auth_header, secret):
        raise AppError(4010, "Webhook 签名无效", 401)

    try:
        payload = await request.json()
    except Exception:
        raise AppError(4000, "请求体不是有效 JSON", 400)

    await apply_revenuecat_event(db, payload)
    return ok(None)
