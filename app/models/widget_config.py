"""首页可编辑系统工具栏 — 组件配置

PRD 3.3 行 264-285 / 9.6 行 658
- 默认组件：学习密度 / 学习周期 / 项目进度 / 待复习
- 可添加：知识负荷 / Focus / 闪卡 / 课程进度 / 奖励 / 商店 / 错题 / 考试倒计时
- 长按编辑 / 拖动排序 / 加号添加 / 垃圾桶删除
- Agent 不负责首页组件编辑（PRD 行 280）

迁移：alembic 019_v2_widgets
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PgEnum
from app.core.database import Base


# create_type=True 让 tests 的 metadata.create_all 自动建枚举；
# 生产路径走 Alembic 迁移（raw SQL）
WIDGET_KIND = PgEnum(
    "study_density", "study_cycle", "project_progress", "review_due",
    "knowledge_load", "focus_today", "flashcard_stats",
    "curriculum_progress", "rewards_overview", "shop_link",
    "mistakes_count", "exam_countdown",
    name="widget_kind", create_type=True,
)
WIDGET_SIZE = PgEnum(
    "small", "medium", "large",
    name="widget_size", create_type=True,
)


class WidgetConfig(Base):
    """单个用户的单个首页组件配置实例。"""
    __tablename__ = "widget_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    kind: Mapped[str] = mapped_column(WIDGET_KIND, nullable=False)
    size: Mapped[str] = mapped_column(WIDGET_SIZE, nullable=False, server_default="small")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 组件自定义配置（如关联的 project_id / subject 等）
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
