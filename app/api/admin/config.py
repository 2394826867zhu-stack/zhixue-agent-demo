"""A-14/C-22 · 全局配置 + 系统公告管理端点（admin）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.admin_auth import get_current_admin
from app.schemas.config import ConfigUpdate
from app.schemas.envelope import Envelope
from app.services import config_service

router = APIRouter()


def ok(data):
    return {"code": 200, "message": "success", "data": data}


def _dump(cfg):
    return {
        "feature_flags": cfg.feature_flags,
        "min_app_version": cfg.min_app_version,
        "announcement": cfg.announcement,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


@router.get("/config", summary="读取全局配置", response_model=Envelope[dict])
async def admin_get_config(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    cfg = await config_service.get_config(db)
    await db.commit()
    return ok(_dump(cfg))


@router.patch("/config", summary="更新全局配置 + 系统公告", response_model=Envelope[dict])
async def admin_update_config(
    body: ConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin),
):
    cfg = await config_service.update_config(db, body.model_dump(exclude_unset=True))
    await db.commit()
    return ok(_dump(cfg))
