"""create notes, knowledge_points, flashcards tables

Revision ID: 002
Revises: 001
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # notes
    op.create_table(
        "notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_input", sa.Text, nullable=True),
        sa.Column("source_file_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("full_version", sa.Text, nullable=True),
        sa.Column("exam_version", sa.Text, nullable=True),
        sa.Column("graph_mermaid", sa.Text, nullable=True),
        sa.Column("difficulty_points", JSONB, nullable=False, server_default="[]"),
        sa.Column("flashcards_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_index("ix_notes_user_subject", "notes", ["user_id", "subject"])

    # knowledge_points
    op.create_table(
        "knowledge_points",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("key_formula", sa.Text, nullable=True),
        sa.Column("bloom_level", sa.String(20), nullable=False, server_default="remember"),
        sa.Column("mastery_status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_kp_user_id", "knowledge_points", ["user_id"])
    op.create_index("ix_kp_user_subject", "knowledge_points", ["user_id", "subject"])
    op.create_index("ix_kp_mastery", "knowledge_points", ["user_id", "mastery_status"])

    # flashcards
    op.create_table(
        "flashcards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_point_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_type", sa.String(20), nullable=False),
        sa.Column("front", sa.Text, nullable=False),
        sa.Column("back", sa.Text, nullable=False),
        sa.Column("stability", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("difficulty", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("due_date", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("review_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rating", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_flashcards_user_due", "flashcards", ["user_id", "due_date"])
    op.create_index("ix_flashcards_kp", "flashcards", ["knowledge_point_id"])


def downgrade() -> None:
    op.drop_table("flashcards")
    op.drop_table("knowledge_points")
    op.drop_table("notes")
