"""审计 L6 · 时间戳列收紧为 NOT NULL，对齐模型意图

alembic check 报 9 个时间戳列 modify_nullable(existing=True→new=False)：模型用
`Mapped[datetime]`（非 Optional → NOT NULL），但这些列的迁移当初建成 nullable。
模型意图是对的（这些列恒由 default/server_default 填充，永不为空），是 DB 松了。
本迁移把 DB 收紧成 NOT NULL 对齐模型（防御性先 backfill NULL→NOW() 再 SET NOT NULL）。

Revision ID: 049
Revises: 048
Create Date: 2026-06-03
"""
from alembic import op

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None

# (表, 列)
_COLS = [
    ("app_config", "updated_at"),
    ("faq_items", "updated_at"),
    ("feedback", "created_at"),
    ("kb_files", "created_at"),
    ("kb_files", "updated_at"),
    ("subscription_events", "created_at"),
    ("support_messages", "created_at"),
    ("support_threads", "last_message_at"),
    ("support_threads", "created_at"),
]


def upgrade() -> None:
    for table, col in _COLS:
        # 防御：理论上恒被填充，但对历史脏数据兜底，避免 SET NOT NULL 失败。
        op.execute(f'UPDATE {table} SET {col} = NOW() WHERE {col} IS NULL')
        op.alter_column(table, col, nullable=False)


def downgrade() -> None:
    for table, col in _COLS:
        op.alter_column(table, col, nullable=True)
