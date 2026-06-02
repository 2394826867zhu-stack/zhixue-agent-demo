"""E-12 · Study Cowork Schema。"""
from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field("共同专注", max_length=50)


class Heartbeat(BaseModel):
    state: str = Field("idle", pattern="^(focusing|break|idle)$")
    focus_minutes: int = Field(0, ge=0, le=100000)


class RoomMember(BaseModel):
    """房间成员在线 presence（Redis 存储，字段给默认值容忍 presence 变动）。"""
    uid: str
    display_name: str = ""
    state: str = "idle"
    focus_minutes: int = 0
    joined_at: int = 0
    updated_at: int = 0


class RoomSnapshot(BaseModel):
    code: str
    name: str
    host_id: str
    created_at: int
    members: list[RoomMember]
    member_count: int
