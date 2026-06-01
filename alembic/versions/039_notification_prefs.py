"""C-21 · 用户通知偏好字段

Revision ID: 039
Revises: 038
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("flashcard_reminder_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("daily_reminder_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("daily_reminder_time", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_reminder_time")
    op.drop_column("users", "daily_reminder_enabled")
    op.drop_column("users", "flashcard_reminder_enabled")
    op.drop_column("users", "push_enabled")
