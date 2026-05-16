"""create daily_tasks and pomodoro_records tables

Revision ID: 006
Revises: 005
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_date", sa.Date, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column("source_ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("estimated_minutes", sa.Integer, nullable=False, server_default="25"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("ai_priority_score", sa.Float, nullable=False, server_default="50.0"),
        sa.Column("ai_priority_reason", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_daily_tasks_user_date", "daily_tasks", ["user_id", "task_date"])
    op.create_index("ix_daily_tasks_status", "daily_tasks", ["user_id", "status"])

    op.create_table(
        "pomodoro_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("daily_tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_pomodoro_user_date", "pomodoro_records", ["user_id", "record_date"])


def downgrade() -> None:
    op.drop_table("pomodoro_records")
    op.drop_table("daily_tasks")
