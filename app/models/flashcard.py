import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Text, DateTime, Date, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
from app.core.database import Base

NOTEBOOK_ORIGIN = PgEnum("official", "user_project", name="project_source", create_type=False)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True)

    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'concept' | 'formula' | 'application'

    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)

    # FSRS fields
    stability: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 1=完全不会 2=模糊 3=基本会 4=熟练

    # FSRS state string: 'New'|'Learning'|'Review'|'Relearning'
    fsrs_state: Mapped[str] = mapped_column(String(20), default="New", nullable=False)

    # v2 PRD · 项目挂载 + 来源区分（migration 020）
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    notebook_origin: Mapped[str] = mapped_column(NOTEBOOK_ORIGIN, nullable=False, server_default="user_project")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # v0.33 P0-1 · 24h 首次复习推送时间戳（NULL=未推过，非 NULL=已推过不再推）
    first_review_pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relations
    knowledge_point: Mapped["KnowledgePoint"] = relationship("KnowledgePoint", back_populates="flashcards")

    @property
    def memory_state(self) -> str:
        from datetime import timedelta
        today = date.today()
        if self.review_count == 0:
            return "new"
        if self.due_date <= today:
            return "overdue"
        if self.due_date <= today + timedelta(days=1):
            return "due_soon"
        return "safe"

    def __repr__(self) -> str:
        return f"<Flashcard {self.card_type} kp={self.knowledge_point_id}>"
