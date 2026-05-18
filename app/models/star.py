import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

COSMETIC_CATALOG: dict[str, dict] = {
    "material_holographic": {"name": "全息材质", "category": "material", "price": 300, "preview_url": ""},
    "material_matte_dark": {"name": "哑光暗色", "category": "material", "price": 150, "preview_url": ""},
    "material_metallic": {"name": "金属光泽", "category": "material", "price": 200, "preview_url": ""},
    "accessory_graduation_hat": {"name": "学士帽", "category": "accessory", "price": 120, "preview_url": ""},
    "accessory_headphones": {"name": "耳机", "category": "accessory", "price": 100, "preview_url": ""},
    "accessory_wings_gold": {"name": "金翅膀", "category": "accessory", "price": 500, "preview_url": ""},
    "accessory_backpack": {"name": "小书包", "category": "accessory", "price": 80, "preview_url": ""},
    "aura_aurora": {"name": "极光光环", "category": "aura", "price": 250, "preview_url": ""},
    "aura_nebula": {"name": "星云光环", "category": "aura", "price": 350, "preview_url": ""},
    "aura_pixel_rain": {"name": "像素雨", "category": "aura", "price": 200, "preview_url": ""},
    "voice_deep": {"name": "低沉音调", "category": "voice", "price": 150, "preview_url": ""},
    "voice_bright": {"name": "清亮音调", "category": "voice", "price": 150, "preview_url": ""},
}

STAR_REWARDS: dict[str, int] = {
    "lesson_complete": 30,
    "daily_goal": 50,
    "streak_day": 20,   # multiplied by min(streak_days, 7)
    "flashcard_review": 2,  # per card, daily cap 100
    "achievement": 0,   # variable, set per achievement
    "invite_friend": 200,
}


class StarLedger(Base):
    __tablename__ = "star_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # positive = earned, negative = spent

    reason: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # 'lesson_complete' | 'flashcard_review' | 'streak' | 'achievement' | 'cosmetic_purchase' | 'daily_goal' | 'invite_friend'

    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # additional context e.g. {"session_id": "...", "achievement_name": "..."}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class UserCosmetic(Base):
    __tablename__ = "user_cosmetics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, primary_key=True)
    # key from COSMETIC_CATALOG

    equipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
