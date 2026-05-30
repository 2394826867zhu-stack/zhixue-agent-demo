"""首页 widget_config 服务 — v2 PRD 3.3 / 9.6

- 默认 4 个：学习密度 / 学习周期 / 项目进度 / 待复习
- 长按编辑 + 拖动排序 + 加号添加 + 垃圾桶删除（Agent 不负责）
"""
import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.models.widget_config import WidgetConfig
from app.schemas.widget import (
    WidgetCreate, WidgetUpdateItem, WidgetBatchUpdate,
    WidgetCatalog, WidgetCatalogItem,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


# ── 可添加组件清单（PRD 行 270）──────────────────────────────────────
_CATALOG: list[WidgetCatalogItem] = [
    WidgetCatalogItem(kind="study_density",       title="学习密度",   description="本周每天的学习强度",         is_default=True,  available_sizes=["small", "medium"]),
    WidgetCatalogItem(kind="study_cycle",         title="学习周期",   description="当前学习周期进度",             is_default=True,  available_sizes=["small", "medium"]),
    WidgetCatalogItem(kind="project_progress",    title="项目进度",   description="主项目完成度",                 is_default=True,  available_sizes=["small", "medium", "large"]),
    WidgetCatalogItem(kind="review_due",          title="待复习",     description="待复习闪卡数量",               is_default=True,  available_sizes=["small"]),
    WidgetCatalogItem(kind="knowledge_load",      title="知识负荷",   description="近期新增知识点数量",           is_default=False, available_sizes=["small"]),
    WidgetCatalogItem(kind="focus_today",         title="沉浸今日",   description="今日番茄钟累计时长",           is_default=False, available_sizes=["small", "medium"]),
    WidgetCatalogItem(kind="flashcard_stats",     title="闪卡概览",   description="闪卡总量 / FSRS 状态",         is_default=False, available_sizes=["small"]),
    WidgetCatalogItem(kind="curriculum_progress", title="课程进度",   description="官方课程当前章节",             is_default=False, available_sizes=["medium"]),
    WidgetCatalogItem(kind="rewards_overview",    title="奖励",       description="知星余额 + 最近收入",          is_default=False, available_sizes=["small"]),
    WidgetCatalogItem(kind="shop_link",           title="商店",       description="装扮商店入口",                 is_default=False, available_sizes=["small"]),
    WidgetCatalogItem(kind="mistakes_count",      title="错题数",     description="错题本待处理数量",             is_default=False, available_sizes=["small"]),
    WidgetCatalogItem(kind="exam_countdown",      title="考试倒计时", description="最近一场考试距今天数",         is_default=False, available_sizes=["small", "medium"]),
]


class WidgetService:

    def get_catalog(self) -> WidgetCatalog:
        return WidgetCatalog(items=_CATALOG)

    async def list_user_widgets(
        self, db: AsyncSession, user_id: str,
    ) -> list[WidgetConfig]:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(WidgetConfig)
            .where(WidgetConfig.user_id == uid)
            .order_by(WidgetConfig.sort_order.asc(), WidgetConfig.created_at.asc())
        )
        widgets = list(result.scalars().all())
        if not widgets:
            # 新用户首次进入，初始化默认 4 组件
            widgets = await self._init_defaults(db, uid)
        return widgets

    async def batch_update(
        self, db: AsyncSession, user_id: str, req: WidgetBatchUpdate,
    ) -> list[WidgetConfig]:
        uid = uuid.UUID(user_id)

        # remove
        if req.remove:
            await db.execute(
                delete(WidgetConfig).where(
                    WidgetConfig.user_id == uid,
                    WidgetConfig.id.in_(req.remove),
                )
            )

        # update
        for u in req.update:
            values: dict = {}
            if u.sort_order is not None:
                values["sort_order"] = u.sort_order
            if u.is_visible is not None:
                values["is_visible"] = u.is_visible
            if u.size is not None:
                values["size"] = u.size
            if u.config is not None:
                values["config"] = u.config
            if values:
                await db.execute(
                    update(WidgetConfig)
                    .where(WidgetConfig.id == u.id, WidgetConfig.user_id == uid)
                    .values(**values)
                )

        # add
        for a in req.add:
            db.add(WidgetConfig(
                user_id=uid,
                kind=a.kind,
                size=a.size,
                sort_order=a.sort_order,
                config=a.config,
            ))

        await db.commit()

        result = await db.execute(
            select(WidgetConfig)
            .where(WidgetConfig.user_id == uid)
            .order_by(WidgetConfig.sort_order.asc())
        )
        return list(result.scalars().all())

    # ── 内部 ──────────────────────────────────────────────────────────

    async def _init_defaults(
        self, db: AsyncSession, uid: uuid.UUID,
    ) -> list[WidgetConfig]:
        """新用户首次进入，按 PRD 9.6 行 658 初始化 4 个默认组件。"""
        defaults = [c for c in _CATALOG if c.is_default]
        for idx, item in enumerate(defaults):
            db.add(WidgetConfig(
                user_id=uid,
                kind=item.kind,
                size="small",
                sort_order=idx,
                is_visible=True,
            ))
        await db.commit()
        result = await db.execute(
            select(WidgetConfig)
            .where(WidgetConfig.user_id == uid)
            .order_by(WidgetConfig.sort_order.asc())
        )
        return list(result.scalars().all())


widget_service = WidgetService()
