"""v0.34 P1-4 · feynman_attempts ORM"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, SmallInteger, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class FeynmanAttempt(Base):
    __tablename__ = "feynman_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kp_id = Column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False)
    ss_session_id = Column(UUID(as_uuid=True), ForeignKey("studyspace_sessions.id", ondelete="SET NULL"), nullable=True)

    user_explanation = Column(Text, nullable=False)

    accuracy_score = Column(SmallInteger, nullable=True)
    completeness_score = Column(SmallInteger, nullable=True)
    clarity_score = Column(SmallInteger, nullable=True)
    total_score = Column(SmallInteger, nullable=True)
    gaps = Column(JSONB, server_default=text("'[]'::jsonb"))
    ai_feedback = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, server_default="pending")

    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    graded_at = Column(DateTime(timezone=True), nullable=True)
