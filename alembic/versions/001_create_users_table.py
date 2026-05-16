"""create users table

Revision ID: 001
Revises:
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(50), nullable=True),
        sa.Column("grade", sa.String(20), nullable=True),
        sa.Column("subjects", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("plan_type", sa.String(20), nullable=False, server_default="free"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
