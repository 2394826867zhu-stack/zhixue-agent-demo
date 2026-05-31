"""学习内核 P1 · 先修知识图谱地基（prerequisite_edges）

Revision ID: 038
Revises: 037
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prerequisite_edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_kp_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_kp_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="llm"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_prereq_user", "prerequisite_edges", ["user_id"])
    op.create_index("ix_prereq_from", "prerequisite_edges", ["from_kp_id"])
    op.create_index("ix_prereq_to", "prerequisite_edges", ["to_kp_id"])
    op.create_unique_constraint("uq_prereq_edge", "prerequisite_edges", ["from_kp_id", "to_kp_id"])


def downgrade() -> None:
    op.drop_constraint("uq_prereq_edge", "prerequisite_edges", type_="unique")
    op.drop_index("ix_prereq_to", "prerequisite_edges")
    op.drop_index("ix_prereq_from", "prerequisite_edges")
    op.drop_index("ix_prereq_user", "prerequisite_edges")
    op.drop_table("prerequisite_edges")
