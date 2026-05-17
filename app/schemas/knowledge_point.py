import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, field_validator

BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
MASTERY_STATUSES = {"new", "learning", "reviewing", "mastered"}


class KnowledgePointCreate(BaseModel):
    name: str
    subject: str | None = None
    content: str | None = None
    key_formula: str | None = None
    bloom_level: str = "remember"
    tags: list[str] = []

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("知识点名称不能为空")
        if len(v) > 255:
            raise ValueError("名称不能超过255字符")
        return v.strip()

    @field_validator("bloom_level")
    @classmethod
    def valid_bloom(cls, v: str) -> str:
        if v not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level 必须为: {', '.join(BLOOM_LEVELS)}")
        return v


class KnowledgePointUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    content: str | None = None
    key_formula: str | None = None
    bloom_level: str | None = None
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            if not v.strip():
                raise ValueError("知识点名称不能为空")
            return v.strip()
        return v

    @field_validator("bloom_level")
    @classmethod
    def valid_bloom(cls, v: str | None) -> str | None:
        if v is not None and v not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level 必须为: {', '.join(BLOOM_LEVELS)}")
        return v


class KnowledgePointResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    note_id: uuid.UUID | None
    name: str
    subject: str | None
    content: str | None
    key_formula: str | None
    bloom_level: str
    mastery_status: str
    tags: list
    flashcard_count: int = 0
    next_review_date: str | None = None   # ISO date，最早到期闪卡日期
    stability: float | None = None        # 对应闪卡的 FSRS stability
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class KnowledgePointStats(BaseModel):
    total: int
    new: int
    learning: int
    reviewing: int
    mastered: int
    by_subject: dict[str, int] = {}
