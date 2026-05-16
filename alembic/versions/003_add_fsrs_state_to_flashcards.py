"""add fsrs_state column to flashcards

Revision ID: 003
Revises: 002
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "flashcards",
        sa.Column("fsrs_state", sa.String(20), nullable=False, server_default="New"),
    )


def downgrade() -> None:
    op.drop_column("flashcards", "fsrs_state")
