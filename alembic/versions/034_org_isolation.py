"""企业隔离层 · users.org_id + document_embeddings.org_id

Revision ID: 034
Revises: 033
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("org_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.add_column(
        "document_embeddings", sa.Column("org_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_doc_embed_org_id", "document_embeddings", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_doc_embed_org_id", "document_embeddings")
    op.drop_column("document_embeddings", "org_id")
    op.drop_index("ix_users_org_id", "users")
    op.drop_column("users", "org_id")
