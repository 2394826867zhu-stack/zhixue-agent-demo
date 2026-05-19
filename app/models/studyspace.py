import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class StudySpaceSession(Base):
    __tablename__ = "studyspace_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # nullable: mock_exam sessions have no chapter
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_chapters.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # 'active' | 'paused' | 'completed'

    session_type: Mapped[str] = mapped_column(String(20), default="lesson", nullable=False)
    # 'lesson' | 'mock_exam'

    exam_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # mock_exam only: {"subject": "数学", "exam_type": "gaokao", "duration_minutes": 120}

    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    kp_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flashcards_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stars_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
