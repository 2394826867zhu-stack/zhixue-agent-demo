"""onboarding sessions and check-ins

Revision ID: 011
Revises: 010
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add onboarding_completed flag to users
    op.add_column("users", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("learning_profile", JSONB, nullable=True))

    # Onboarding sessions (one per user)
    op.create_table(
        "onboarding_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("current_step", sa.String(30), nullable=False, server_default="grade"),
        sa.Column("profile_draft", JSONB, nullable=False, server_default="{}"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_onboarding_sessions_user_id", "onboarding_sessions", ["user_id"])

    # Daily check-ins
    op.create_table(
        "check_ins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_content", sa.Text, nullable=False),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("parsed_updates", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_check_ins_user_id", "check_ins", ["user_id"])
    op.create_index("ix_check_ins_created_at", "check_ins", ["created_at"])


def downgrade() -> None:
    op.drop_table("check_ins")
    op.drop_table("onboarding_sessions")
    op.drop_column("users", "learning_profile")
    op.drop_column("users", "onboarding_completed")
