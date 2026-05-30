"""v0.34 P1-2 · user_skill_levels ORM"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UserSkillLevel(Base):
    __tablename__ = "user_skill_levels"
    __table_args__ = (UniqueConstraint("user_id", "subject", name="uq_user_skill_subject"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject = Column(String(50), nullable=False)
    current_bloom = Column(String(20), nullable=False, server_default="remember")
    consecutive_correct = Column(Integer, nullable=False, server_default="0")
    consecutive_wrong = Column(Integer, nullable=False, server_default="0")
    total_correct = Column(Integer, nullable=False, server_default="0")
    total_questions = Column(Integer, nullable=False, server_default="0")
    last_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
