import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator

NODE_TYPES = {"lesson", "review", "training", "project"}
NODE_STATUSES = {"locked", "current", "done", "review"}


class PathNodeOut(BaseModel):
    id: uuid.UUID
    stage_id: uuid.UUID
    title: str
    node_type: str
    status: str
    subject: str | None
    estimated_minutes: int
    reward: str | None
    note_id: uuid.UUID | None
    kp_ids: list[uuid.UUID]
    prerequisite_ids: list[uuid.UUID]
    sort_order: int
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class PathStageOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    sort_order: int
    progress: float             # 0.0–1.0，已完成节点比例
    is_ai_generated: bool
    nodes: list[PathNodeOut] = []
    model_config = {"from_attributes": True}


class PathNodeCreate(BaseModel):
    stage_id: str
    title: str
    node_type: str = "lesson"
    subject: str | None = None
    estimated_minutes: int = 30
    reward: str | None = None
    note_id: str | None = None
    kp_ids: list[str] = []
    prerequisite_ids: list[str] = []

    @field_validator("node_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in NODE_TYPES:
            raise ValueError(f"node_type 必须为: {', '.join(NODE_TYPES)}")
        return v

    @field_validator("estimated_minutes")
    @classmethod
    def valid_minutes(cls, v: int) -> int:
        if not 1 <= v <= 480:
            raise ValueError("预估时间必须在 1-480 分钟之间")
        return v


class PathStageCreate(BaseModel):
    title: str
    description: str = ""


class PathGenerateRequest(BaseModel):
    subjects: list[str] = []   # 空 = 根据用户现有 KP 自动判断
    goal: str = ""              # 用户目标描述（可选）


class CoachTipOut(BaseModel):
    message: str
    suggested_node_id: uuid.UUID | None
    suggested_action: str | None   # "start" | "review" | "continue"
