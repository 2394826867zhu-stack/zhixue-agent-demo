import uuid
from datetime import datetime, date
from pydantic import BaseModel, field_validator


class FlashcardResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    knowledge_point_id: uuid.UUID
    card_type: str
    front: str
    back: str
    stability: float
    difficulty: float
    due_date: date
    review_count: int
    last_review: datetime | None
    last_rating: int | None
    fsrs_state: str
    memory_state: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    rating: int

    @field_validator("rating")
    @classmethod
    def valid_rating(cls, v: int) -> int:
        if v not in (1, 2, 3, 4):
            raise ValueError("评分必须为 1(完全不会) 2(模糊) 3(基本会) 4(熟练)")
        return v


class ReviewResponse(BaseModel):
    flashcard_id: uuid.UUID
    next_due_date: date
    new_stability: float
    new_difficulty: float
    interval_days: int
    fsrs_state: str
    mastery_status_updated: bool
