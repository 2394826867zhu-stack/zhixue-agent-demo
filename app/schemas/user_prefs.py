"""用户偏好 Schemas — v2 PRD 9.11 + C-21 通知偏好"""
import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class UserPrefsOut(BaseModel):
    theme_mode: Literal["auto", "light", "dark"]
    dynamic_type_scale: float
    reduced_motion: bool
    haptics_enabled: bool
    voice_enabled: bool
    # C-21 通知偏好
    push_enabled: bool
    flashcard_reminder_enabled: bool
    daily_reminder_enabled: bool
    daily_reminder_time: str | None  # "HH:MM" e.g. "20:00"; None = not set


class UserPrefsUpdate(BaseModel):
    theme_mode: Literal["auto", "light", "dark"] | None = None
    dynamic_type_scale: float | None = Field(default=None, ge=0.8, le=1.4)
    reduced_motion: bool | None = None
    haptics_enabled: bool | None = None
    voice_enabled: bool | None = None
    # C-21 通知偏好
    push_enabled: bool | None = None
    flashcard_reminder_enabled: bool | None = None
    daily_reminder_enabled: bool | None = None
    daily_reminder_time: str | None = None

    @field_validator("daily_reminder_time")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("daily_reminder_time must be HH:MM (e.g. '20:00')")
        return v
