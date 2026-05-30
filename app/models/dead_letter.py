"""死信任务表（F-11）：Celery 任务重试耗尽后的最终失败记录，供管理员排查。"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class DeadLetterTask(Base):
    __tablename__ = "dead_letter_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(155), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # {args, kwargs}
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
