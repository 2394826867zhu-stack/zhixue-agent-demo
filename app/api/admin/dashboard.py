from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.envelope import Envelope
from app.schemas.admin_responses import DashboardOut, InboxSummaryOut
from app.services.admin_service import admin_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/dashboard", summary="后台总览数据", response_model=Envelope[DashboardOut])
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_dashboard(db))


@router.get("/inbox-summary", summary="待办聚合（到达通知，供轮询）", response_model=Envelope[InboxSummaryOut])
async def get_inbox_summary(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_inbox_summary(db))
