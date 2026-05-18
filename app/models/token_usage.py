import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

# USD cost per 1M tokens by model
TOKEN_PRICES: dict[str, dict[str, float]] = {
    "deepseek-chat":    {"prompt": 0.14,  "completion": 0.28},
    "claude-opus-4-7":  {"prompt": 3.0,   "completion": 15.0},
    "gpt-4o":           {"prompt": 2.5,   "completion": 10.0},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = TOKEN_PRICES.get(model, {"prompt": 0.5, "completion": 1.5})
    return (prompt_tokens * prices["prompt"] + completion_tokens * prices["completion"]) / 1_000_000


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_token_usage_user_date", "user_id", "created_at"),
    )
