import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PgEnum, JSONB
from app.core.database import Base

# 引用 018 已创建的 enum（不重复创建）
NOTEBOOK_ORIGIN = PgEnum("official", "user_project", name="project_source", create_type=False)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'ai_generated' | 'image' | 'pdf' | 'text'

    source_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ai_generated时：用户输入的主题描述
    # text时：粘贴的文字内容

    source_file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # image/pdf时：上传文件的存储路径

    status: Mapped[str] = mapped_column(String(20), default="processing", nullable=False)
    # 'processing' | 'done' | 'failed'

    # 三件套输出
    full_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    exam_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    graph_mermaid: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 提取结果
    difficulty_points: Mapped[list] = mapped_column(JSONB, default=list)
    # [{"name": "...", "reason": "..."}]

    # 闪卡是否已生成（用于前端提示按钮状态）
    flashcards_generated: Mapped[bool] = mapped_column(default=False)

    # v2 PRD · 项目挂载 + 来源区分（migration 020）
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    notebook_origin: Mapped[str] = mapped_column(NOTEBOOK_ORIGIN, nullable=False, server_default="user_project")
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relations
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship("KnowledgePoint", back_populates="note", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Note {self.title or self.id}>"
