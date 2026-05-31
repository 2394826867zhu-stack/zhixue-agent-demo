"""E 可观测 · rag_retrieval_traces ORM

每次 RAG 召回的质量指标落库（不落原始 query，只记长度），供运维聚合分析：
零召回率 / score 分布 / doc_kind 命中分布，数据驱动检索与上下文迭代。
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, Numeric, DateTime, text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class RagRetrievalTrace(Base):
    __tablename__ = "rag_retrieval_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)

    # 召回来源场景：auto_inject（每条消息自动注入 top-5）/ tool（retrieve_knowledge 工具）
    source = Column(String(30), nullable=False, server_default="auto_inject")

    query_len = Column(Integer, nullable=False, server_default="0")
    hit_count = Column(Integer, nullable=False, server_default="0")
    is_empty = Column(Boolean, nullable=False, server_default=text("false"))

    score_max = Column(Numeric(6, 4), nullable=True)
    score_min = Column(Numeric(6, 4), nullable=True)
    score_avg = Column(Numeric(6, 4), nullable=True)

    kind_distribution = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
