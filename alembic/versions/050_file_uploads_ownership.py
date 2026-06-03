"""审计 L5 · file_uploads 归属表（文件下载 owner 隔离，杜绝 IDOR）

GET /v1/files/{filename} 此前仅校验登录、不校验归属——任何登录用户知道他人随机
文件名即可下载（IDOR）。本表记录 stored_filename → user_id，下载端点据此校验。

Revision ID: 050
Revises: 049
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_uploads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_file_uploads_user_id", "file_uploads", ["user_id"])
    op.create_unique_constraint("uq_file_uploads_stored_filename", "file_uploads", ["stored_filename"])


def downgrade() -> None:
    op.drop_constraint("uq_file_uploads_stored_filename", "file_uploads", type_="unique")
    op.drop_index("ix_file_uploads_user_id", table_name="file_uploads")
    op.drop_table("file_uploads")
