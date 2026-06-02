"""E-06 · 帮助中心 FAQ Schema。"""
import uuid
from pydantic import BaseModel, Field


class FaqItemOut(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    sort_order: int
    model_config = {"from_attributes": True}


class FaqCategoryGroup(BaseModel):
    category: str
    items: list[FaqItemOut]


class FaqListResponse(BaseModel):
    categories: list[FaqCategoryGroup]


# ---- admin ----
class FaqItemCreate(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    question: str = Field(..., min_length=1, max_length=300)
    answer: str = Field(..., min_length=1)
    sort_order: int = 0
    is_published: bool = True


class FaqItemUpdate(BaseModel):
    category: str | None = Field(None, min_length=1, max_length=50)
    question: str | None = Field(None, min_length=1, max_length=300)
    answer: str | None = Field(None, min_length=1)
    sort_order: int | None = None
    is_published: bool | None = None
