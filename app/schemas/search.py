"""C-09 全局搜索 Schemas。"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SearchType = Literal["flashcard", "note", "knowledge_point", "mistake", "project"]


class SearchResultItem(BaseModel):
    type: SearchType
    id: uuid.UUID
    title: str
    snippet: str | None = None
    subject: str | None = None
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[SearchResultItem]
