"""A-14/C-22 · 客户端远程配置端点：GET /v1/config。

返回 feature flags（功能开关/灰度）+ min_app_version（强制更新下限）+ 系统公告（仅 active）。
前端启动时拉取，据此开关功能 / 提示升级 / 展示公告。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services import config_service

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", summary="客户端远程配置（feature flags + 强制更新 + 系统公告）")
async def get_app_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = await config_service.get_config(db)
    return {"code": 200, "message": "success", "data": config_service.public_config(cfg)}
