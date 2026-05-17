"""add agent_memory to users

Revision ID: 012
Revises: 011
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("agent_memory", JSONB, nullable=True, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("users", "agent_memory")
