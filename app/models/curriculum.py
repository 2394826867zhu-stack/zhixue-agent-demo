import uuid
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from app.core.database import Base


class CurriculumChapter(Base):
    __tablename__ = "curriculum_chapters"

    # 系统 seed 内容（owner_user_id IS NULL）的唯一键 —— 防双 worker 并发 seed 造重复
    # （见 migration 053）。用户导入内容不受约束。
    __table_args__ = (
        Index(
            "uq_curriculum_system_seed_key",
            "subject", "grade_type", "grade_year", "semester",
            "chapter_index", "lesson_index", "textbook_version",
            unique=True,
            postgresql_where=text("owner_user_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    grade_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # junior_high / senior_high / college
    grade_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1 / 2 / 3
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1 / 2
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(100), nullable=False)
    lesson_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_title: Mapped[str] = mapped_column(String(150), nullable=False)
    textbook_version: Mapped[str] = mapped_column(String(30), nullable=False, default="人教版A")
    is_key: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 重点考查章节
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    # 'system' | 'user_import'
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
