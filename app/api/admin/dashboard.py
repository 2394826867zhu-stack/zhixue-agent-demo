from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.services.admin_service import admin_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/dashboard", summary="后台总览数据")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    return ok(await admin_service.get_dashboard(db))
