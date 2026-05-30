"""v0.30 · agent_tool_traces ORM"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, Numeric, text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class AgentToolTrace(Base):
    __tablename__ = "agent_tool_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    message_id = Column(UUID(as_uuid=True), nullable=True)

    tool_name = Column(String(60), nullable=False)
    arguments = Column(JSONB, server_default=text("'{}'::jsonb"))
    result_summary = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    latency_ms = Column(Integer, nullable=True)

    status = Column(String(20), nullable=False, server_default="success")
    error_message = Column(Text, nullable=True)

    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)

    was_helpful = Column(Boolean, nullable=True)
    user_action = Column(String(20), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
