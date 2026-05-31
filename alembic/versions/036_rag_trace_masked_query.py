"""E→B 闭环 · rag_retrieval_traces.masked_query（低质召回脱敏 query 采集）

Revision ID: 036
Revises: 035
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_retrieval_traces", sa.Column("masked_query", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rag_retrieval_traces", "masked_query")
