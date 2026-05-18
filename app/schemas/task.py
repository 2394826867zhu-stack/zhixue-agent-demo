import uuid
from datetime import datetime, date
from pydantic import BaseModel, computed_field, field_validator, model_validator


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

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("任务名称不能为空")
        return v

    @field_validator("estimated_minutes")
    @classmethod
    def valid_minutes(cls, v: int | None) -> int | None:
        if v is not None and not 1 <= v <= 480:
            raise ValueError("预估时间必须在 1-480 分钟之间")
        return v

    @field_validator("sort_order")
    @classmethod
    def valid_sort_order(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("排序值不能小于0")
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

    @computed_field
    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @computed_field
    @property
    def duration(self) -> int:
        return self.estimated_minutes


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

    @model_validator(mode="after")
    def valid_time_range(self) -> "PomodoroCreate":
        if self.completed_at < self.started_at:
            raise ValueError("结束时间不能早于开始时间")
        return self


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
    sessions: int       # 本周番茄钟次数
    focus_minutes: int  # 本周专注分钟数
    streak_days: int    # 连续学习天数
