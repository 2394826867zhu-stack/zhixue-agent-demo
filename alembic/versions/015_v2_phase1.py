"""v2 phase1: studyspace_sessions, notifications, star_ledger, user_cosmetics, task source fields

Revision ID: 015
Revises: 014
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # studyspace_sessions
    op.create_table(
        "studyspace_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", UUID(as_uuid=True), sa.ForeignKey("curriculum_chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kp_extracted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("flashcards_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_studyspace_sessions_user_id", "studyspace_sessions", ["user_id"])
    op.create_index("ix_studyspace_sessions_chapter_id", "studyspace_sessions", ["chapter_id"])

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("related_action", sa.String(100), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_notification_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    # star_ledger
    op.create_table(
        "star_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_star_ledger_user_id", "star_ledger", ["user_id"])
    op.create_index("ix_star_ledger_reason", "star_ledger", ["reason"])
    op.create_index("ix_star_ledger_created_at", "star_ledger", ["created_at"])

    # user_cosmetics
    op.create_table(
        "user_cosmetics",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, primary_key=True),
        sa.Column("item_id", sa.String(100), nullable=False, primary_key=True),
        sa.Column("equipped", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # extend daily_tasks with source + auto_complete_trigger
    op.add_column("daily_tasks", sa.Column("source", sa.String(20), nullable=False, server_default="user"))
    op.add_column("daily_tasks", sa.Column("auto_complete_trigger", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("daily_tasks", "auto_complete_trigger")
    op.drop_column("daily_tasks", "source")
    op.drop_table("user_cosmetics")
    op.drop_table("star_ledger")
    op.drop_table("notifications")
    op.drop_table("studyspace_sessions")
