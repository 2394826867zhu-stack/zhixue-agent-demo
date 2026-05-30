"""StudySpace 画板 Schemas — v2 PRD 9.3 行 636"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class CanvasStrokeIn(BaseModel):
    # F-09：path_d 限 SVG path 合法字符（命令字母 + 数字 + 分隔符），防注入任意文本
    path_d: str = Field(
        min_length=1,
        max_length=20000,
        pattern=r"^[MmLlHhVvCcSsQqTtAaZz0-9.,\s+\-eE]+$",
    )
    # F-09：color 限 hex 颜色（#RGB / #RGBA / #RRGGBB / #RRGGBBAA），防脏数据/注入
    color: str = Field(
        default="#1F2937",
        pattern=r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
    )
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
