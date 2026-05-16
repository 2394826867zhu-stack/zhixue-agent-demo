import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class TrainingStartRequest(BaseModel):
    mode: str
    knowledge_point_id: str | None = None
    subject: str | None = None
    question_count: int = 5

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("single_kp", "subject"):
            raise ValueError("mode 必须为 single_kp 或 subject")
        return v

    @field_validator("question_count")
    @classmethod
    def valid_count(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("题目数量必须在 1-20 之间")
        return v


class TrainingQuestionOut(BaseModel):
    id: uuid.UUID
    knowledge_point_id: uuid.UUID
    bloom_level: str
    question_type: str
    question_text: str
    reference_answer: str | None = None
    user_answer: str | None
    ai_score: int | None
    ai_feedback: str | None
    is_wrong: bool
    answered_at: datetime | None
    model_config = {"from_attributes": True}


class TrainingSessionOut(BaseModel):
    id: uuid.UUID
    mode: str
    subject: str | None
    knowledge_point_id: uuid.UUID | None
    status: str
    question_count: int
    answered_count: int
    avg_score: float | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class TrainingSessionDetail(TrainingSessionOut):
    questions: list[TrainingQuestionOut] = []


class AnswerRequest(BaseModel):
    user_answer: str

    @field_validator("user_answer")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("答案不能为空")
        return v.strip()


class AnswerResult(BaseModel):
    question_id: uuid.UUID
    ai_score: int
    ai_feedback: str
    is_wrong: bool
    reference_answer: str
    session_completed: bool
    session_avg_score: float | None
