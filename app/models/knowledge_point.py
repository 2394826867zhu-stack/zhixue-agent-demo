import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
from app.core.database import Base

NOTEBOOK_ORIGIN = PgEnum("official", "user_project", name="project_source", create_type=False)
DIFFICULTY_TIER = PgEnum("blue", "purple", "gold", name="node_difficulty", create_type=False)


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("curriculum_chapters.id", ondelete="SET NULL"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Markdown：定义 + 公式 + 例子

    key_formula: Mapped[str | None] = mapped_column(Text, nullable=True)

    bloom_level: Mapped[str] = mapped_column(String(20), default="remember", nullable=False)
    # 'remember'|'understand'|'apply'|'analyze'|'evaluate'|'create'

    mastery_status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)
    # 'new'|'learning'|'reviewing'|'mastered'

    tags: Mapped[list] = mapped_column(JSON, default=list)

    # v2 PRD · 项目挂载 + 来源区分 + 蓝紫金分级（migration 020）
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    notebook_origin: Mapped[str] = mapped_column(NOTEBOOK_ORIGIN, nullable=False, server_default="user_project")
    difficulty_tier: Mapped[str] = mapped_column(DIFFICULTY_TIER, nullable=False, server_default="blue", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relations
    note: Mapped["Note"] = relationship("Note", back_populates="knowledge_points")
    chapter: Mapped["CurriculumChapter | None"] = relationship("CurriculumChapter")
    flashcards: Mapped[list["Flashcard"]] = relationship("Flashcard", back_populates="knowledge_point", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<KnowledgePoint {self.name}>"
