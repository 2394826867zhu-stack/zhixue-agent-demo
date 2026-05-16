import uuid
from datetime import datetime
from pydantic import BaseModel


class MistakeOut(BaseModel):
    id: uuid.UUID
    knowledge_point_id: uuid.UUID
    bloom_level: str
    question_type: str
    question_text: str
    reference_answer: str
    user_answer: str | None
    ai_score: int | None
    ai_feedback: str | None
    answered_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class MistakeStatsOut(BaseModel):
    total: int
    by_subject: dict[str, int]
    top_kps: list[dict]  # [{"kp_id": ..., "kp_name": ..., "count": ...}]


class RetryQuestionOut(BaseModel):
    retry_question_id: uuid.UUID
    original_question_id: uuid.UUID
    question_type: str
    bloom_level: str
    question_text: str


class RetryAnswerResult(BaseModel):
    retry_question_id: uuid.UUID
    ai_score: int
    ai_feedback: str
    reference_answer: str
    mistake_resolved: bool
