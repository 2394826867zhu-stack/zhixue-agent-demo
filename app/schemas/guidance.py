import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class GuidanceStartRequest(BaseModel):
    question: str
    subject: str | None = None

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("问题不能为空")
        if len(v) > 1000:
            raise ValueError("问题不能超过1000字")
        return v.strip()


class ChatRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("消息不能为空")
        if len(v) > 1000:
            raise ValueError("消息不能超过1000字")
        return v.strip()


class GuidanceMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    linked_kp_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class GuidanceSessionOut(BaseModel):
    id: uuid.UUID
    title: str
    subject: str | None
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class GuidanceSessionDetail(GuidanceSessionOut):
    messages: list[GuidanceMessageOut] = []


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    message: GuidanceMessageOut
