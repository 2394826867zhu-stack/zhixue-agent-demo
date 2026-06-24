"""F2 · projects.framework_status：知识框架构建态（building/ready/failed）

v3 纯生成式框架：建项目后初始化完整框架（加载态），加载完才放行进入。
存量项目 server_default='ready'（不被卡在加载态）；新项目由 create() 显式置 'building'。
String 而非 enum，避免 enum 迁移痛。

Revision ID: 054
Revises: 053
Create Date: 2026-06-25
"""
import sqlalchemy as sa
from alembic import op


revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("framework_status", sa.String(length=20), nullable=False,
                  server_default="ready"),
    )


def downgrade() -> None:
    op.drop_column("projects", "framework_status")
