import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, JSON, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 学习信息
    grade: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'junior_high' | 'senior_high' | 'college'
    subjects: Mapped[list] = mapped_column(JSON, default=list)

    # 引导对话
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    learning_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_memory: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # 语音设置
    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # v0.25 · UI 偏好（PRD 9.11 + ui-ux brief）
    theme_mode: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="auto",
    )  # "auto" | "light" | "dark"
    dynamic_type_scale: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0",
    )  # 0.8 - 1.4 适配 iOS Dynamic Type
    reduced_motion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    haptics_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )

    # 推送通知
    expo_push_token: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # C-21 · 通知偏好
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    flashcard_reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    daily_reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    daily_reminder_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"

    # 多租户（F/企业隔离层）：所属机构；个人用户为 NULL。先不加 FK，组织实体表后续
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # 套餐
    plan_type: Mapped[str] = mapped_column(String(20), default="free")
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # E-04 · 7 天 Pro 试用：每人仅一次。trial_used 防重复领取；
    # trial_ends_at 在未来则当前 Pro 来自试用（状态区分试用 vs 付费）。
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # E-10 · 邀请好友：referral_code 懒生成（首次访问邀请页时填充，全局唯一）；
    # referred_by 记录是谁邀请了我（每人仅能填一次，防自荐）。
    referral_code: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True, index=True)
    referred_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
