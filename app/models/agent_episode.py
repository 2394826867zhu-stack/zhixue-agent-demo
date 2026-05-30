"""v0.29 · agent_episodes ORM 模型"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, SmallInteger, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

from app.core.database import Base


class AgentEpisode(Base):
    __tablename__ = "agent_episodes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=True)

    event_kind = Column(String(40), nullable=False)
    summary = Column(Text, nullable=False)
    detail = Column(JSONB, server_default=text("'{}'::jsonb"))

    ref_kp_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    ref_note_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    ref_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)

    importance = Column(SmallInteger, nullable=False, server_default="5")
    emotional_tone = Column(String(20), nullable=True)

    embedding_id = Column(UUID(as_uuid=True), nullable=True)

    occurred_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    def __repr__(self) -> str:
        return f"<AgentEpisode {self.event_kind} u={self.user_id} imp={self.importance}>"
