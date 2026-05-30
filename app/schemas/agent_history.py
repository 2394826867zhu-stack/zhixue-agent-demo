"""Agent 浏览记录 + 搜索 Schemas — v2 PRD 9.7"""
import uuid
from datetime import datetime
from pydantic import BaseModel


class ConversationLogItem(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    last_message_preview: str | None
    message_count: int
    tools_called: dict
    started_at: datetime
    last_activity_at: datetime
    model_config = {"from_attributes": True}


class ConversationLogList(BaseModel):
    items: list[ConversationLogItem]
    total: int
    page: int
    page_size: int


class ConversationSearchResult(BaseModel):
    items: list[ConversationLogItem]
    query: str
    total: int
