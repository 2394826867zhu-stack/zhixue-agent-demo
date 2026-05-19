"""v2.1: curriculum import, mock exam, voice, file upload

Revision ID: 016
Revises: 015
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── uploaded_files ──────────────────────────────────────────────────────
    op.create_table(
        "uploaded_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False, server_default="image"),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_uploaded_files_user_id", "uploaded_files", ["user_id"])

    # ── users: voice_enabled ────────────────────────────────────────────────
    op.add_column("users", sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default="false"))

    # ── curriculum_chapters: source + owner_user_id ─────────────────────────
    op.add_column("curriculum_chapters", sa.Column("source", sa.String(20), nullable=False, server_default="system"))
    op.add_column("curriculum_chapters", sa.Column("owner_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_curriculum_chapters_owner_user_id", "curriculum_chapters", ["owner_user_id"])

    # ── studyspace_sessions: session_type + exam_config + nullable chapter ──
    op.add_column("studyspace_sessions", sa.Column("session_type", sa.String(20), nullable=False, server_default="lesson"))
    op.add_column("studyspace_sessions", sa.Column("exam_config", JSONB, nullable=True))
    op.alter_column("studyspace_sessions", "chapter_id", nullable=True)

    # ── training_sessions: session_type + studyspace_session_id ────────────
    op.add_column("training_sessions", sa.Column("session_type", sa.String(20), nullable=False, server_default="kp_practice"))
    op.add_column("training_sessions", sa.Column(
        "studyspace_session_id",
        UUID(as_uuid=True),
        sa.ForeignKey("studyspace_sessions.id", ondelete="SET NULL"),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("training_sessions", "studyspace_session_id")
    op.drop_column("training_sessions", "session_type")
    op.alter_column("studyspace_sessions", "chapter_id", nullable=False)
    op.drop_column("studyspace_sessions", "exam_config")
    op.drop_column("studyspace_sessions", "session_type")
    op.drop_index("ix_curriculum_chapters_owner_user_id", "curriculum_chapters")
    op.drop_column("curriculum_chapters", "owner_user_id")
    op.drop_column("curriculum_chapters", "source")
    op.drop_column("users", "voice_enabled")
    op.drop_index("ix_uploaded_files_user_id", "uploaded_files")
    op.drop_table("uploaded_files")
