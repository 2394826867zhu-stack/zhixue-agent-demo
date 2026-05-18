import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["通知"])
_svc = NotificationService()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="未读通知列表")
async def get_unread(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_unread(db, str(user.id)))


@router.get("/all", summary="全部通知（含已读）")
async def get_all(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _svc.get_all(db, str(user.id), page, page_size))


@router.post("/{notification_id}/read", summary="标记单条已读")
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.mark_read(db, str(user.id), notification_id)
    return ok(None)


@router.post("/read-all", summary="全部标记已读")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _svc.mark_all_read(db, str(user.id))
    return ok(None)
