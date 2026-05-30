"""F-11 · Celery 死信队列表 dead_letter_tasks

Revision ID: 033
Revises: 032
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dead_letter_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("task_name", sa.String(200), nullable=False),
        sa.Column("task_id", sa.String(155), nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text, nullable=False, server_default=""),
        sa.Column("traceback", sa.Text, nullable=True),
        sa.Column("retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "resolved", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_dlt_task_name", "dead_letter_tasks", ["task_name"])
    op.create_index("ix_dlt_task_id", "dead_letter_tasks", ["task_id"])
    op.create_index("ix_dlt_resolved", "dead_letter_tasks", ["resolved"])
    op.create_index("ix_dlt_created_at", "dead_letter_tasks", ["created_at"])


def downgrade() -> None:
    op.drop_table("dead_letter_tasks")
