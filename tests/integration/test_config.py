"""A-14/C-22 · 全局配置单例 get/update 集成测试。"""
import pytest

from app.services import config_service

pytestmark = pytest.mark.asyncio


async def test_get_config_creates_singleton(db):
    cfg = await config_service.get_config(db)
    assert cfg.id == 1
    assert cfg.feature_flags == {}


async def test_update_config_partial(db):
    await config_service.get_config(db)
    cfg = await config_service.update_config(db, {
        "min_app_version": "1.5.0",
        "feature_flags": {"new_search": True},
    })
    assert cfg.min_app_version == "1.5.0"
    assert cfg.feature_flags["new_search"] is True
    # 未传 announcement → 保持 None（局部更新）
    assert cfg.announcement is None


async def test_update_announcement_then_clear(db):
    await config_service.get_config(db)
    c1 = await config_service.update_config(db, {
        "announcement": {"title": "新功能上线", "body": "全局搜索已上线", "level": "info", "active": True},
    })
    assert c1.announcement["title"] == "新功能上线"
    # 显式传 null 清除公告
    c2 = await config_service.update_config(db, {"announcement": None})
    assert c2.announcement is None
