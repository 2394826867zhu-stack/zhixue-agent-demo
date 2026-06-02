from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.admin import UpdateUserRequest
from app.schemas.envelope import Envelope
from app.services.admin_service import admin_service

router = APIRouter(prefix="/users")


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="用户列表", response_model=Envelope[dict])
async def list_users(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.list_users(db, search, page, page_size))


@router.get("/{user_id}", summary="用户详情", response_model=Envelope[dict])
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_user_detail(db, user_id))


@router.patch("/{user_id}", summary="更新用户配额/状态", response_model=Envelope[dict])
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.update_user(db, user_id, body))
