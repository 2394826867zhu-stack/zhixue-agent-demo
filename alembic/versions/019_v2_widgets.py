"""v2 PRD · 首页可编辑系统工具栏 widget_configs

PRD 3.3（行 264-285）/ 9.6（行 658）
- 默认 4 个：学习密度 / 学习周期 / 项目进度 / 待复习
- 可添加：知识负荷 / Focus / 闪卡 / 课程进度 / 奖励 / 商店 / 错题 / 考试倒计时

Revision ID: 019
Revises: 018
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


widget_kind_enum = postgresql.ENUM(
    "study_density", "study_cycle", "project_progress", "review_due",
    "knowledge_load", "focus_today", "flashcard_stats",
    "curriculum_progress", "rewards_overview", "shop_link",
    "mistakes_count", "exam_countdown",
    name="widget_kind", create_type=False,
)
widget_size_enum = postgresql.ENUM("small", "medium", "large", name="widget_size", create_type=False)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE widget_kind AS ENUM ("
        "'study_density','study_cycle','project_progress','review_due',"
        "'knowledge_load','focus_today','flashcard_stats',"
        "'curriculum_progress','rewards_overview','shop_link',"
        "'mistakes_count','exam_countdown')"
    )
    op.execute("CREATE TYPE widget_size AS ENUM ('small','medium','large')")

    op.create_table(
        "widget_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", widget_kind_enum, nullable=False),
        sa.Column("size", widget_size_enum, nullable=False, server_default="small"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_widget_configs_user_id", "widget_configs", ["user_id"])
    op.create_index("ix_widget_configs_user_sort", "widget_configs", ["user_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_widget_configs_user_sort", "widget_configs")
    op.drop_index("ix_widget_configs_user_id", "widget_configs")
    op.drop_table("widget_configs")
    op.execute("DROP TYPE IF EXISTS widget_size")
    op.execute("DROP TYPE IF EXISTS widget_kind")
