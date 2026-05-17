import uuid
from datetime import datetime, date
from pydantic import BaseModel, field_validator, computed_field


class ExamCreate(BaseModel):
    name: str
    subject: str | None = None
    exam_date: date
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("考试名称不能为空")
        if len(v) > 100:
            raise ValueError("考试名称不能超过100字")
        return v

    @field_validator("exam_date")
    @classmethod
    def date_not_past(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("考试日期不能早于今天")
        return v


class ExamUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    exam_date: date | None = None
    notes: str | None = None

    @field_validator("exam_date")
    @classmethod
    def date_not_past(cls, v: date | None) -> date | None:
        if v is not None and v < date.today():
            raise ValueError("考试日期不能早于今天")
        return v


class ExamOut(BaseModel):
    id: uuid.UUID
    name: str
    subject: str | None
    exam_date: date
    notes: str | None
    created_at: datetime

    @computed_field
    @property
    def days_remaining(self) -> int:
        return max(0, (self.exam_date - date.today()).days)

    @computed_field
    @property
    def urgency(self) -> str:
        d = self.days_remaining
        if d == 0:
            return "today"
        if d <= 3:
            return "critical"
        if d <= 7:
            return "urgent"
        if d <= 30:
            return "normal"
        return "relaxed"

    model_config = {"from_attributes": True}


class CountdownItem(BaseModel):
    exam: ExamOut
    ai_tip: str | None = None   # 只有最近一场考试才有 AI 建议


class CountdownOut(BaseModel):
    upcoming: list[CountdownItem]   # 按日期升序，最多 5 场
    has_exam_today: bool
