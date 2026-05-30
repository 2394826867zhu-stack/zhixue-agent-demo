"""用户 UI 偏好 Schemas — v2 PRD 9.11"""
from typing import Literal
from pydantic import BaseModel, Field


class UserPrefsOut(BaseModel):
    theme_mode: Literal["auto", "light", "dark"]
    dynamic_type_scale: float
    reduced_motion: bool
    haptics_enabled: bool
    voice_enabled: bool


class UserPrefsUpdate(BaseModel):
    theme_mode: Literal["auto", "light", "dark"] | None = None
    dynamic_type_scale: float | None = Field(default=None, ge=0.8, le=1.4)
    reduced_motion: bool | None = None
    haptics_enabled: bool | None = None
    voice_enabled: bool | None = None
