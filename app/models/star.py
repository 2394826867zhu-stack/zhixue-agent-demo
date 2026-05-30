import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

# v2 PRD 9.10 行 693 装扮分类：衣服 / 发饰 / 配饰 / 背景
# 三套默认服装由 starter_outfit_id 标识，新用户自动解锁

COSMETIC_CATALOG: dict[str, dict] = {
    # ── 衣服 clothing ───────────────────────────────────────────────
    # 三套默认服装（PRD 9.10 行 693 starter set）
    "clothing_default_white_tee":   {"name": "素色 T 恤",       "category": "clothing", "price": 0,   "is_starter": True,  "outfit_set": "starter_a", "preview_url": ""},
    "clothing_default_navy_hoodie": {"name": "藏青连帽衫",       "category": "clothing", "price": 0,   "is_starter": True,  "outfit_set": "starter_b", "preview_url": ""},
    "clothing_default_uniform":     {"name": "校服衬衫",         "category": "clothing", "price": 0,   "is_starter": True,  "outfit_set": "starter_c", "preview_url": ""},
    "clothing_mint_oversize":       {"name": "薄荷绿宽松卫衣",   "category": "clothing", "price": 180, "preview_url": ""},
    "clothing_ice_blue_jacket":     {"name": "冰蓝外套",         "category": "clothing", "price": 240, "preview_url": ""},
    "clothing_silver_techwear":     {"name": "银光机能服",       "category": "clothing", "price": 380, "preview_url": ""},

    # ── 发饰 hair ───────────────────────────────────────────────────
    "hair_default_short":   {"name": "短发（默认）",   "category": "hair", "price": 0,   "is_starter": True, "outfit_set": "starter_a", "preview_url": ""},
    "hair_default_pony":    {"name": "马尾",           "category": "hair", "price": 0,   "is_starter": True, "outfit_set": "starter_b", "preview_url": ""},
    "hair_default_braided": {"name": "麻花辫",         "category": "hair", "price": 0,   "is_starter": True, "outfit_set": "starter_c", "preview_url": ""},
    "hair_bow_pink":        {"name": "粉色蝴蝶结",     "category": "hair", "price": 80,  "preview_url": ""},
    "hair_hairpin_star":    {"name": "小星星发夹",     "category": "hair", "price": 60,  "preview_url": ""},
    "hair_headband_mint":   {"name": "薄荷绿发箍",     "category": "hair", "price": 70,  "preview_url": ""},

    # ── 配饰 accessory ──────────────────────────────────────────────
    "accessory_headphones_white":  {"name": "白色耳机", "category": "accessory", "price": 0,   "is_starter": True, "outfit_set": "starter_a", "preview_url": ""},
    "accessory_glasses":           {"name": "圆框眼镜", "category": "accessory", "price": 0,   "is_starter": True, "outfit_set": "starter_b", "preview_url": ""},
    "accessory_book":              {"name": "小书本",   "category": "accessory", "price": 0,   "is_starter": True, "outfit_set": "starter_c", "preview_url": ""},
    "accessory_graduation_hat":    {"name": "学士帽",   "category": "accessory", "price": 120, "preview_url": ""},
    "accessory_wings_gold":        {"name": "金翅膀",   "category": "accessory", "price": 500, "preview_url": ""},
    "accessory_backpack":          {"name": "小书包",   "category": "accessory", "price": 80,  "preview_url": ""},

    # ── 背景 background ─────────────────────────────────────────────
    "background_default_desk":     {"name": "书桌房间（默认）",   "category": "background", "price": 0,   "is_starter": True, "outfit_set": "starter_a", "preview_url": ""},
    "background_default_dorm":     {"name": "宿舍",               "category": "background", "price": 0,   "is_starter": True, "outfit_set": "starter_b", "preview_url": ""},
    "background_default_library":  {"name": "图书馆角落",         "category": "background", "price": 0,   "is_starter": True, "outfit_set": "starter_c", "preview_url": ""},
    "background_cafe":             {"name": "咖啡馆窗边",         "category": "background", "price": 220, "preview_url": ""},
    "background_night_city":       {"name": "夜景窗台",           "category": "background", "price": 280, "preview_url": ""},
    "background_aurora":           {"name": "极光房间",           "category": "background", "price": 360, "preview_url": ""},
}


# 三套默认服装定义（PRD 9.10 行 693）
STARTER_OUTFITS: dict[str, dict] = {
    "starter_a": {
        "name": "学院基础",
        "items": ["clothing_default_white_tee", "hair_default_short",
                  "accessory_headphones_white", "background_default_desk"],
    },
    "starter_b": {
        "name": "夜读放松",
        "items": ["clothing_default_navy_hoodie", "hair_default_pony",
                  "accessory_glasses", "background_default_dorm"],
    },
    "starter_c": {
        "name": "图书馆少女",
        "items": ["clothing_default_uniform", "hair_default_braided",
                  "accessory_book", "background_default_library"],
    },
}


def get_starter_item_ids() -> list[str]:
    """所有标记 is_starter=True 的 item_id 列表（新用户解锁）。"""
    return [k for k, v in COSMETIC_CATALOG.items() if v.get("is_starter")]

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
