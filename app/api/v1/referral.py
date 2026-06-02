"""E-10 · 邀请好友端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.referral import ReferralInfo, RedeemRequest, RedeemResult
from app.services import referral_service

router = APIRouter(prefix="/referral", tags=["邀请好友"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="我的邀请码 + 已邀请人数")
async def get_referral(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    info = await referral_service.get_info(db, user)
    return ok(ReferralInfo(**info).model_dump())


@router.post("/redeem", summary="填写好友邀请码（每人一次，双方得知星）")
async def redeem_referral(
    body: RedeemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await referral_service.redeem(db, user, body.code)
    return ok(RedeemResult(**result).model_dump())
