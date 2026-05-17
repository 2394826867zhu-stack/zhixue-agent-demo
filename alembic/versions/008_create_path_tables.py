"""create path tables

Revision ID: 008
Revises: 007
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "path_stages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_path_stages_user_id", "path_stages", ["user_id"])

    op.create_table(
        "path_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", UUID(as_uuid=True), sa.ForeignKey("path_stages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="locked"),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column("estimated_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("reward", sa.String(255), nullable=True),
        sa.Column("note_id", UUID(as_uuid=True), sa.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kp_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("prerequisite_ids", ARRAY(UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_path_nodes_user_id", "path_nodes", ["user_id"])
    op.create_index("ix_path_nodes_stage_id", "path_nodes", ["stage_id"])


def downgrade() -> None:
    op.drop_table("path_nodes")
    op.drop_table("path_stages")
