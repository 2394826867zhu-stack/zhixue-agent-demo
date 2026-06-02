"""E-06 · 帮助中心 FAQ 端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import faq_service

router = APIRouter(prefix="/faq", tags=["帮助中心"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="帮助中心 FAQ（按分类分组，仅已发布）")
async def get_faq(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = await faq_service.list_published(db)
    return ok(data.model_dump(mode="json"))
