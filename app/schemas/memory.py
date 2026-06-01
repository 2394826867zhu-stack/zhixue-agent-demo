"""C-15 · 记忆面板 Schema"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MemoryItemOut(BaseModel):
    id: uuid.UUID
    event_kind: str
    summary: str
    importance: int
    emotional_tone: Optional[str]
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
