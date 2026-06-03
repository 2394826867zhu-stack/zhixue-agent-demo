import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class FileUpload(Base):
    """已上传文件的归属记录（审计 L5：文件下载 owner 级隔离）。

    上传时记录 stored_filename → user_id；GET /v1/files/{filename} 据此校验归属，
    杜绝 IDOR（此前仅校验登录、不校验归属，知道他人随机文件名即可下载）。
    """
    __tablename__ = "file_uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
