"""E 可观测 · rag_retrieval_traces（召回质量埋点落库）

Revision ID: 035
Revises: 034
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_retrieval_traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="auto_inject"),
        sa.Column("query_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_empty", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score_max", sa.Numeric(6, 4), nullable=True),
        sa.Column("score_min", sa.Numeric(6, 4), nullable=True),
        sa.Column("score_avg", sa.Numeric(6, 4), nullable=True),
        sa.Column("kind_distribution", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_rag_trace_created_at", "rag_retrieval_traces", ["created_at"])
    op.create_index("ix_rag_trace_user_id", "rag_retrieval_traces", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_trace_user_id", "rag_retrieval_traces")
    op.drop_index("ix_rag_trace_created_at", "rag_retrieval_traces")
    op.drop_table("rag_retrieval_traces")
