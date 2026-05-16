"""add retry fields to training_questions, make session_id nullable

Revision ID: 005
Revises: 004
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # session_id nullable so retry questions don't need a session
    op.alter_column("training_questions", "session_id", nullable=True)

    op.add_column("training_questions", sa.Column(
        "is_retry", sa.Boolean, nullable=False, server_default="false"
    ))
    op.add_column("training_questions", sa.Column(
        "original_question_id", UUID(as_uuid=True),
        sa.ForeignKey("training_questions.id", ondelete="SET NULL"),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("training_questions", "original_question_id")
    op.drop_column("training_questions", "is_retry")
    op.alter_column("training_questions", "session_id", nullable=False)
