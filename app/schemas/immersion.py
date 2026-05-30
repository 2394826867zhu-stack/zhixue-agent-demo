"""沉浸模式 + Agent 状态 Schemas — v2 PRD 6.1 / 9.10"""
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


SCENE_KIND_T = Literal["desk_room", "library", "cafe", "tech_space"]
IMMERSION_STATUS_T = Literal["active", "paused", "completed", "abandoned"]
AGENT_STATE_T = Literal[
    "idle", "thinking", "speaking", "focus", "celebrate", "reward",
    "remind", "sleepy", "confused", "error",
]


class SceneOut(BaseModel):
    id: uuid.UUID
    kind: SCENE_KIND_T
    title: str
    description: str
    background_url: str | None
    bgm_url: str | None
    white_noise_url: str | None
    is_default: bool
    is_premium: bool
    sort_order: int
    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    scene_id: uuid.UUID | None = None  # 空则用默认场景
    focus_minutes: int = Field(default=25, ge=5, le=120)
    break_minutes: int = Field(default=5, ge=1, le=30)
    long_break_minutes: int = Field(default=15, ge=5, le=60)
    cycle_count: int = Field(default=4, ge=1, le=10)
    bgm_enabled: bool = True
    white_noise_enabled: bool = False


class SessionPatch(BaseModel):
    status: IMMERSION_STATUS_T | None = None
    pomodoros_completed: int | None = Field(default=None, ge=0)
    total_focus_minutes: int | None = Field(default=None, ge=0)
    bgm_enabled: bool | None = None
    white_noise_enabled: bool | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    scene_id: uuid.UUID
    status: IMMERSION_STATUS_T
    focus_minutes: int
    break_minutes: int
    long_break_minutes: int
    cycle_count: int
    pomodoros_completed: int
    total_focus_minutes: int
    bgm_enabled: bool
    white_noise_enabled: bool
    started_at: datetime
    ended_at: datetime | None
    model_config = {"from_attributes": True}


# ── Agent 状态机 ──────────────────────────────────────────────

class AgentStateOut(BaseModel):
    current_state: AGENT_STATE_T
    state_data: dict
    last_transition_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AgentStateUpdate(BaseModel):
    """Agent 状态变更 — 通常由服务端触发，前端少用。
    PRD 行 168 状态：idle/thinking/speaking/focus/celebrate/reward 等。
    """
    current_state: AGENT_STATE_T
    state_data: dict = {}
