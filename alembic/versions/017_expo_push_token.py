"""add expo push token to users

Revision ID: 017
Revises: 016
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("expo_push_token", sa.String(200), nullable=True),
    )
    op.create_index("ix_users_expo_push_token", "users", ["expo_push_token"])


def downgrade() -> None:
    op.drop_index("ix_users_expo_push_token", "users")
    op.drop_column("users", "expo_push_token")
