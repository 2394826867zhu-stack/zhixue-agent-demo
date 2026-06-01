import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum
from app.core.database import Base

KB_FILE_TYPE = PgEnum("pdf", "docx", "txt", name="kb_file_type", create_type=True)
KB_FILE_STATUS = PgEnum("pending", "processing", "done", "failed", name="kb_file_status", create_type=True)


class KnowledgeBaseFile(Base):
    __tablename__ = "kb_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # UUID hex + ext on disk
    file_type: Mapped[str] = mapped_column(KB_FILE_TYPE, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    processing_status: Mapped[str] = mapped_column(
        KB_FILE_STATUS, nullable=False, default="pending", index=True
    )
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBaseFile {self.original_name} ({self.processing_status})>"
