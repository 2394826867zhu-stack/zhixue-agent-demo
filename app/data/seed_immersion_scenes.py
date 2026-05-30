"""沉浸场景 seed — v0.27 F-01

PRD 6.1 行 576-579：第一版场景 = 书桌/房间，可与商店/装扮联动。
v0.27 同步 4 个背景资产（与 cosmetic_catalog 的 background 类目对齐）。

注：本 seed 仅写 scenes 元数据；真实图片 / BGM 文件由前端 / CDN 提供。
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.immersion import ImmersionScene

logger = logging.getLogger(__name__)


_SCENES = [
    {
        "kind": "desk_room",
        "title": "书桌房间",
        "description": "同桌自习的默认场景，柔光台灯下安静学习。",
        "background_url": None,
        "bgm_url": None,
        "white_noise_url": None,
        "is_default": True,
        "is_premium": False,
        "sort_order": 0,
    },
    {
        "kind": "library",
        "title": "图书馆角落",
        "description": "纸张沙沙、笔尖摩擦的午后图书馆。",
        "background_url": None,
        "bgm_url": None,
        "white_noise_url": None,
        "is_default": False,
        "is_premium": True,   # 解锁需购买（对应 background_default_library 已 starter，但额外资产付费）
        "sort_order": 1,
    },
    {
        "kind": "cafe",
        "title": "咖啡馆窗边",
        "description": "雨天靠窗，咖啡机偶尔轻响。",
        "background_url": None,
        "bgm_url": None,
        "white_noise_url": None,
        "is_default": False,
        "is_premium": True,
        "sort_order": 2,
    },
    {
        "kind": "tech_space",
        "title": "夜景科技空间",
        "description": "城市天际线 + 极简桌面。",
        "background_url": None,
        "bgm_url": None,
        "white_noise_url": None,
        "is_default": False,
        "is_premium": True,
        "sort_order": 3,
    },
]


async def seed_immersion_scenes(db: AsyncSession) -> int:
    """幂等：只插入数据库里没有的 kind。"""
    existing_q = await db.execute(select(ImmersionScene.kind))
    existing = {row[0] for row in existing_q.all()}

    inserted = 0
    for scene in _SCENES:
        if scene["kind"] in existing:
            continue
        db.add(ImmersionScene(**scene))
        inserted += 1
    if inserted:
        await db.commit()
        logger.info(f"seeded {inserted} immersion scenes")
    return inserted
