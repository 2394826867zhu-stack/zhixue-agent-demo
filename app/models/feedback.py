"""E-07 · 用户反馈上报：含可选截图 URL + 设备信息 + App 版本。

截图走现有 /v1/files/upload 上传后拿到的相对 URL（screenshot_url），与 feedback 解耦。
device_info 为前端采集的 JSON（平台/系统版本/机型/屏幕等），便于复现 bug。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


# 反馈分类
FEEDBACK_CATEGORIES = ("bug", "suggestion", "praise", "other")
# 处理状态：open=待处理 / triaged=已分类 / resolved=已处理
FEEDBACK_STATUSES = ("open", "triaged", "resolved")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    content: Mapped[str] = mapped_column(Text, nullable=False)

    screenshot_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
