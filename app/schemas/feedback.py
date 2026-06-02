"""E-07 · 用户反馈上报 Schema。"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    category: str = Field("other", pattern="^(bug|suggestion|praise|other)$")
    content: str = Field(..., min_length=1, max_length=4000)
    screenshot_url: str | None = Field(None, max_length=300)
    device_info: dict | None = None
    app_version: str | None = Field(None, max_length=20)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    category: str
    content: str
    screenshot_url: str | None
    device_info: dict | None
    app_version: str | None
    status: str
    admin_note: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ---- admin ----
class FeedbackUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(open|triaged|resolved)$")
    admin_note: str | None = Field(None, max_length=4000)
