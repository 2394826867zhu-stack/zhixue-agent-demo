import uuid
from datetime import datetime, date, timezone
from sqlalchemy import Text, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class CheckIn(Base):
    __tablename__ = "check_ins"
    # P0-1 · 每日签到唯一：杜绝同一天重复签到刷知星（无去重时一天连点 N 次发 20×N 星）。
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_checkin_user_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # 签到归属的"当日"（北京时区日期），唯一约束的去重键
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"kp_updates": [...], "kps_created": [...], "tasks_created": [...]}
    parsed_updates: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
