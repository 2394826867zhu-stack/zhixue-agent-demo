"""首页 widget_config Schemas — v2 PRD 3.3"""
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

WIDGET_KIND_T = Literal[
    "study_density", "study_cycle", "project_progress", "review_due",
    "knowledge_load", "focus_today", "flashcard_stats",
    "curriculum_progress", "rewards_overview", "shop_link",
    "mistakes_count", "exam_countdown",
]

WIDGET_SIZE_T = Literal["small", "medium", "large"]


class WidgetOut(BaseModel):
    id: uuid.UUID
    kind: WIDGET_KIND_T
    size: WIDGET_SIZE_T
    sort_order: int
    is_visible: bool
    config: dict
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class WidgetCreate(BaseModel):
    kind: WIDGET_KIND_T
    size: WIDGET_SIZE_T = "small"
    sort_order: int = 0
    config: dict = {}


class WidgetUpdateItem(BaseModel):
    """批量更新 — 用户长按编辑后一次性提交所有变化。"""
    id: uuid.UUID
    sort_order: int | None = None
    is_visible: bool | None = None
    size: WIDGET_SIZE_T | None = None
    config: dict | None = None


class WidgetBatchUpdate(BaseModel):
    add: list[WidgetCreate] = Field(default_factory=list)
    update: list[WidgetUpdateItem] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)


class WidgetCatalogItem(BaseModel):
    """可添加组件清单（PRD 行 270）"""
    kind: WIDGET_KIND_T
    title: str
    description: str
    is_default: bool  # 是否在新用户初始化时默认添加
    available_sizes: list[WIDGET_SIZE_T]


class WidgetCatalog(BaseModel):
    items: list[WidgetCatalogItem]
