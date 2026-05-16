"""create training_sessions and training_questions tables

Revision ID: 004
Revises: 003
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column("knowledge_point_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("question_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("answered_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_sessions_user_id", "training_sessions", ["user_id"])

    op.create_table(
        "training_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_point_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bloom_level", sa.String(20), nullable=False),
        sa.Column("question_type", sa.String(20), nullable=False),
        sa.Column("question_text", sa.Text, nullable=False),
        sa.Column("reference_answer", sa.Text, nullable=False),
        sa.Column("user_answer", sa.Text, nullable=True),
        sa.Column("ai_score", sa.Integer, nullable=True),
        sa.Column("ai_feedback", sa.Text, nullable=True),
        sa.Column("is_wrong", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_training_questions_session_id", "training_questions", ["session_id"])
    op.create_index("ix_training_questions_wrong", "training_questions", ["user_id", "is_wrong"])


def downgrade() -> None:
    op.drop_table("training_questions")
    op.drop_table("training_sessions")
