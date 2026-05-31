import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Boolean, Float, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
from app.core.database import Base

NOTEBOOK_ORIGIN = PgEnum("official", "user_project", name="project_source", create_type=False)


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'single_kp' | 'subject'

    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)
    knowledge_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # 'active' | 'completed'

    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # v0.27 Q-05 · 显式 StudySpace 挂载（前端传 ss_session_id 时绑定）
    ss_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studyspace_sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questions: Mapped[list["TrainingQuestion"]] = relationship("TrainingQuestion", back_populates="session", cascade="all, delete-orphan")


class TrainingQuestion(Base):
    __tablename__ = "training_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False)

    bloom_level: Mapped[str] = mapped_column(String(20), nullable=False)
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'fill_blank' | 'calculation' | 'essay'

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)

    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 0-100
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_wrong: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # v0.34 P1-5 · 错误原因 careless / concept / method（NULL = 答对）
    error_reason: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    is_retry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_question_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("training_questions.id", ondelete="SET NULL"), nullable=True)

    # v2 PRD · 项目挂载 + 来源区分（migration 020）
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    notebook_origin: Mapped[str] = mapped_column(NOTEBOOK_ORIGIN, nullable=False, server_default="user_project")

    # 学习内核 P0 · 探针题标记（migration 037）
    is_probe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default=text("false"))  # 是否探针题
    probe_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)        # 探针类型（later tasks 定义取值）

    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session: Mapped["TrainingSession | None"] = relationship("TrainingSession", back_populates="questions")
