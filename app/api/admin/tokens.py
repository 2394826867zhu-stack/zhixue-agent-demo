from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.admin import QuotaUpdateRequest
from app.services.admin_service import admin_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/tokens/stats", summary="Token 用量统计")
async def token_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_token_stats(db, days))


@router.get("/tokens/users/{user_id}", summary="单用户 Token 历史")
async def user_token_history(
    user_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_user_token_history(db, user_id, limit))


@router.get("/quotas/{user_id}", summary="用户当前配额详情（v0.32）")
async def get_quota(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_quota(db, user_id))


@router.put("/quotas/{user_id}", summary="设置用户每日 Token 配额")
async def set_quota(
    user_id: str,
    body: QuotaUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.set_quota(db, user_id, body.daily_token_limit, body.notes))
