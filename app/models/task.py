import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Text, DateTime, Date, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # 'flashcard_review' | 'mistake_review' | 'manual'

    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # points to flashcard/knowledge_point/question depending on task_type

    estimated_minutes: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    # 'high' | 'medium' | 'low'

    ai_priority_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    # 0-100, higher = more urgent; used for ordering
    ai_priority_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # 'pending' | 'in_progress' | 'done' | 'skipped'

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    pomodoro_records: Mapped[list["PomodoroRecord"]] = relationship("PomodoroRecord", back_populates="task")


class PomodoroRecord(Base):
    __tablename__ = "pomodoro_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("daily_tasks.id", ondelete="SET NULL"), nullable=True)

    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    # actual duration (user may customize 25/50min etc.)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    task: Mapped["DailyTask | None"] = relationship("DailyTask", back_populates="pomodoro_records")
