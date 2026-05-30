"""StudySpace 时间线 Schemas — v2 PRD 行 436-448"""
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


NODE_KIND_T = Literal[
    "content", "kp_extracted", "flashcard_result", "training_result",
    "mistake", "reflection", "agent_message", "agent_action",
]


class TimelineNodeOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    kind: NODE_KIND_T
    title: str | None
    content: str | None
    payload: dict
    ref_kp_id: uuid.UUID | None
    ref_flashcard_id: uuid.UUID | None
    ref_training_question_id: uuid.UUID | None
    ref_note_id: uuid.UUID | None
    sort_order: int
    is_editable: bool
    amends_node_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TimelineUserAddRequest(BaseModel):
    """用户主动追加（仅允许 content / reflection 两种）。"""
    kind: Literal["content", "reflection"]
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=10000)


class TimelineNodePatch(BaseModel):
    """编辑时间线节点 — 仅 is_editable=True 的节点可改。"""
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=10000)
