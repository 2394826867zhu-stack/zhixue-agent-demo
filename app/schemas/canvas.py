"""StudySpace 画板 Schemas — v2 PRD 9.3 行 636"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CanvasStrokeIn(BaseModel):
    path_d: str = Field(min_length=1, max_length=20000)
    color: str = "#1F2937"
    stroke_width: float = Field(default=2.0, ge=0.5, le=20.0)
    opacity: float = Field(default=1.0, ge=0.1, le=1.0)
    page_index: int = Field(default=0, ge=0, le=100)
    sort_order: int = 0
    metadata_json: dict = {}


class CanvasStrokeBatch(BaseModel):
    strokes: list[CanvasStrokeIn]


class CanvasStrokeOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    path_d: str
    color: str
    stroke_width: float
    opacity: float
    page_index: int
    sort_order: int
    metadata_json: dict
    created_at: datetime
    model_config = {"from_attributes": True}
