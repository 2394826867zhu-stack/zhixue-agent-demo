import uuid
from datetime import datetime, date
from pydantic import BaseModel, field_validator


class DailyTaskCreate(BaseModel):
    title: str
    subject: str | None = None
    estimated_minutes: int = 25
    task_date: date | None = None  # defaults to today if omitted

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("任务名称不能为空")
        return v.strip()

    @field_validator("estimated_minutes")
    @classmethod
    def valid_minutes(cls, v: int) -> int:
        if not 1 <= v <= 480:
            raise ValueError("预估时间必须在 1-480 分钟之间")
        return v


class DailyTaskUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
    estimated_minutes: int | None = None
    sort_order: int | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str | None) -> str | None:
        if v is not None and v not in ("pending", "in_progress", "done", "skipped"):
            raise ValueError("status 必须为 pending/in_progress/done/skipped")
        return v


class DailyTaskOut(BaseModel):
    id: uuid.UUID
    task_date: date
    title: str
    task_type: str
    subject: str | None
    source_ref_id: uuid.UUID | None
    estimated_minutes: int
    priority: str
    ai_priority_score: float
    ai_priority_reason: str | None
    sort_order: int
    status: str
    completed_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PomodoroCreate(BaseModel):
    task_id: str | None = None
    duration_minutes: int
    started_at: datetime
    completed_at: datetime
    note: str | None = None

    @field_validator("duration_minutes")
    @classmethod
    def valid_duration(cls, v: int) -> int:
        if not 1 <= v <= 120:
            raise ValueError("番茄钟时长必须在 1-120 分钟之间")
        return v


class PomodoroOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    record_date: date
    duration_minutes: int
    started_at: datetime
    completed_at: datetime
    note: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class PomodoroStats(BaseModel):
    today_count: int
    today_minutes: int
    week_count: int
    week_minutes: int
