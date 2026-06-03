"""Add kb_files table for D-06 knowledge base file management.

Revision ID: 040
Revises: 039
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None

# Reference enums (create_type=False → columns just reference, the type is
# created once explicitly below). Using postgresql.ENUM (not the generic
# sa.Enum) because only the dialect type honors create_type=False; the generic
# Enum re-fires CREATE TYPE inside create_table → DuplicateObjectError on a
# clean DB. Matches the working pattern in migration 018.
kb_file_type_enum = postgresql.ENUM(
    "pdf", "docx", "txt", name="kb_file_type", create_type=False
)
kb_file_status_enum = postgresql.ENUM(
    "pending", "processing", "done", "failed",
    name="kb_file_status", create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE kb_file_type AS ENUM ('pdf', 'docx', 'txt')")
    op.execute("CREATE TYPE kb_file_status AS ENUM ('pending', 'processing', 'done', 'failed')")
    op.create_table(
        "kb_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("file_type", kb_file_type_enum, nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("processing_status", kb_file_status_enum, nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_kb_files_user_id", "kb_files", ["user_id"])
    op.create_index("ix_kb_files_project_id", "kb_files", ["project_id"])
    op.create_index("ix_kb_files_processing_status", "kb_files", ["processing_status"])


def downgrade() -> None:
    op.drop_index("ix_kb_files_processing_status", table_name="kb_files")
    op.drop_index("ix_kb_files_project_id", table_name="kb_files")
    op.drop_index("ix_kb_files_user_id", table_name="kb_files")
    op.drop_table("kb_files")
    op.execute("DROP TYPE IF EXISTS kb_file_status")
    op.execute("DROP TYPE IF EXISTS kb_file_type")
