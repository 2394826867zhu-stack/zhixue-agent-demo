"""首页可编辑组件 API — v2 PRD 3.3 / 9.6"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.widget import WidgetOut, WidgetBatchUpdate, WidgetCatalog
from app.services.widget_service import widget_service

router = APIRouter(prefix="/widgets", tags=["首页组件"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="当前用户首页组件配置")
async def list_widgets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    widgets = await widget_service.list_user_widgets(db, str(user.id))
    return ok([WidgetOut.model_validate(w).model_dump(mode="json") for w in widgets])


@router.put("", summary="批量编辑（添加/更新/删除一次提交）")
async def batch_update(
    req: WidgetBatchUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    widgets = await widget_service.batch_update(db, str(user.id), req)
    return ok([WidgetOut.model_validate(w).model_dump(mode="json") for w in widgets])


@router.get("/available", summary="可添加组件清单")
async def list_catalog(
    user: User = Depends(get_current_user),
):
    return ok(widget_service.get_catalog().model_dump())
