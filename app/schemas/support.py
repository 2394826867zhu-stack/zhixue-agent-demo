"""E-05 · 自建客服 Schema。"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class SupportMessageOut(BaseModel):
    id: uuid.UUID
    sender: str  # user | staff | system
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SupportThreadOut(BaseModel):
    id: uuid.UUID
    subject: str
    status: str
    last_message_at: datetime
    created_at: datetime
    last_message_preview: str | None = None
    unread_count: int = 0
    model_config = {"from_attributes": True}


class SupportThreadDetail(BaseModel):
    id: uuid.UUID
    subject: str
    status: str
    last_message_at: datetime
    created_at: datetime
    messages: list[SupportMessageOut]


class ThreadCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=4000)


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


# ---- admin ----
class AdminReplyCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class ThreadStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|pending|resolved|closed)$")
