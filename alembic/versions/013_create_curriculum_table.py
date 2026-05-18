"""create curriculum chapters table

Revision ID: 013
Revises: 012
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "curriculum_chapters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("subject", sa.String(50), nullable=False),
        sa.Column("grade_type", sa.String(30), nullable=False),
        sa.Column("grade_year", sa.Integer, nullable=False),
        sa.Column("semester", sa.Integer, nullable=False),
        sa.Column("chapter_index", sa.Integer, nullable=False),
        sa.Column("chapter_title", sa.String(100), nullable=False),
        sa.Column("lesson_index", sa.Integer, nullable=False),
        sa.Column("lesson_title", sa.String(150), nullable=False),
        sa.Column("textbook_version", sa.String(30), nullable=False, server_default="人教版A"),
        sa.Column("is_key", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_curriculum_subject", "curriculum_chapters", ["subject"])
    op.create_index("ix_curriculum_grade", "curriculum_chapters", ["grade_type", "grade_year", "semester"])

    # Add chapter_id FK to knowledge_points (nullable, no constraint cascade needed)
    op.add_column(
        "knowledge_points",
        sa.Column("chapter_id", UUID(as_uuid=True), sa.ForeignKey("curriculum_chapters.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_kp_chapter_id", "knowledge_points", ["chapter_id"])


def downgrade() -> None:
    op.drop_index("ix_kp_chapter_id", "knowledge_points")
    op.drop_column("knowledge_points", "chapter_id")
    op.drop_table("curriculum_chapters")
