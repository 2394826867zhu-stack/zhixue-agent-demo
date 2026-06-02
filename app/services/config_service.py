"""A-14 远程配置 + C-22 系统公告 service。单例行 id=1。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_config import AppConfig

_SINGLETON_ID = 1
_ALLOWED = ("feature_flags", "min_app_version", "announcement")


async def get_config(db: AsyncSession) -> AppConfig:
    """取全局配置单例；不存在则创建空默认（兼容未跑插入的环境）。"""
    cfg = await db.get(AppConfig, _SINGLETON_ID)
    if cfg is None:
        cfg = AppConfig(id=_SINGLETON_ID, feature_flags={})
        db.add(cfg)
        await db.flush()
    return cfg


async def update_config(db: AsyncSession, updates: dict) -> AppConfig:
    """局部更新单例（仅 updates 中出现的字段，支持显式设 null）。不在此 commit。"""
    cfg = await get_config(db)
    for key in _ALLOWED:
        if key in updates:
            setattr(cfg, key, updates[key])
    await db.flush()
    return cfg


def public_config(cfg: AppConfig) -> dict:
    """对客户端暴露的配置：feature_flags + 强制更新下限 + 仅当 active 的公告。

    纯函数，便于单测。公告未激活（active!=true）时不下发，避免客户端误显示。
    """
    ann = cfg.announcement if (isinstance(cfg.announcement, dict) and cfg.announcement.get("active")) else None
    return {
        "feature_flags": cfg.feature_flags or {},
        "min_app_version": cfg.min_app_version,
        "announcement": ann,
    }
