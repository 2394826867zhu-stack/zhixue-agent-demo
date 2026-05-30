"""v0.28 RAG · document_embeddings ORM 模型

存所有可被 RAG 检索的文档 chunk 向量。
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    notebook_origin = Column(String(20), nullable=True)

    doc_kind = Column(String(30), nullable=False)
    doc_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False, server_default="0")

    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=False)

    doc_metadata = Column(JSONB, server_default=text("'{}'::jsonb"))
    embedding_model = Column(String(50), nullable=False)
    embedding_version = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("doc_kind", "doc_id", "chunk_index", "embedding_model",
                         name="uq_doc_embed_identity"),
    )

    def __repr__(self) -> str:
        return f"<DocumentEmbedding {self.doc_kind}:{self.doc_id}#{self.chunk_index}>"
