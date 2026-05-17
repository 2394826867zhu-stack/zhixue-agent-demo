from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.checkin import CheckInRequest, CheckInOut
from app.services.checkin_service import checkin_service

router = APIRouter(prefix="/checkin", tags=["每日管家签到"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("", summary="发起签到（告诉管家今天学了什么）", response_model=None)
async def create_checkin(
    body: CheckInRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await checkin_service.create_checkin(db, str(user.id), body.content)
    return ok(result.model_dump())


@router.get("/today", summary="今日签到记录（无则返回 null）", response_model=None)
async def get_today(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await checkin_service.get_today(db, str(user.id))
    return ok(result.model_dump() if result else None)


@router.get("/history", summary="历史签到列表（分页）", response_model=None)
async def list_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await checkin_service.list_history(db, str(user.id), page, page_size)
    # serialize items
    result["items"] = [item.model_dump() for item in result["items"]]
    return ok(result)
