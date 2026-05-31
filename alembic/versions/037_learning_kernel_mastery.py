"""学习内核 P0 · 校准化掌握度地基（knowledge_points.p_mastery/last_probe + training_questions.is_probe/probe_kind）

Revision ID: 037
Revises: 036
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_points", sa.Column("p_mastery", sa.Float(), nullable=True))
    op.add_column("knowledge_points", sa.Column("last_probe", JSONB(), nullable=True))
    op.add_column(
        "training_questions",
        sa.Column("is_probe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("training_questions", sa.Column("probe_kind", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("training_questions", "probe_kind")
    op.drop_column("training_questions", "is_probe")
    op.drop_column("knowledge_points", "last_probe")
    op.drop_column("knowledge_points", "p_mastery")
