"""v0.28 RAG MVP · document_embeddings (pgvector + HNSW)

PRD Agent OS 升级 · L2 检索层基础设施。

存所有可被 RAG 检索的文档 chunk 向量：
- doc_kind = kp / note / chapter / guidance / episode 等多态
- user_id 强隔离（official content 可用空 user_id + project_id=NULL）
- HNSW 索引 cosine 距离

向量维度：1024（BGE-M3）

Revision ID: 026
Revises: 025
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 确保 vector extension 已启用（docker pgvector 容器里 0.8.2）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. document_embeddings 主表
    op.create_table(
        "document_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),

        # 隔离 / 筛选键
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=True),  # null = official content
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("notebook_origin", sa.String(20), nullable=True),  # official / user_project

        # 文档身份（多态 FK）
        sa.Column("doc_kind", sa.String(30), nullable=False),  # kp / note / chapter / guidance / episode
        sa.Column("doc_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False, server_default="0"),

        # 内容
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),

        # 元数据 + 模型版本快照
        sa.Column("doc_metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embedding_model", sa.String(50), nullable=False),  # BAAI/bge-m3
        sa.Column("embedding_version", sa.String(20), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),

        sa.UniqueConstraint(
            "doc_kind", "doc_id", "chunk_index", "embedding_model",
            name="uq_doc_embed_identity",
        ),
    )

    # 3. 一般索引
    op.create_index("ix_doc_embed_user", "document_embeddings", ["user_id"])
    op.create_index("ix_doc_embed_project", "document_embeddings", ["project_id"])
    op.create_index("ix_doc_embed_kind", "document_embeddings", ["doc_kind"])
    op.create_index("ix_doc_embed_doc_id", "document_embeddings", ["doc_id"])

    # 4. HNSW 向量索引（cosine 距离）
    # pgvector 0.5+，参数走默认 m=16, ef_construction=64
    op.execute("""
        CREATE INDEX ix_doc_embed_hnsw
        ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_embed_hnsw")
    op.drop_index("ix_doc_embed_doc_id", "document_embeddings")
    op.drop_index("ix_doc_embed_kind", "document_embeddings")
    op.drop_index("ix_doc_embed_project", "document_embeddings")
    op.drop_index("ix_doc_embed_user", "document_embeddings")
    op.drop_table("document_embeddings")
