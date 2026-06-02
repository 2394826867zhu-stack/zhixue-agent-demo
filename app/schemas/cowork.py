"""E-12 · Study Cowork Schema。"""
from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field("共同专注", max_length=50)


class Heartbeat(BaseModel):
    state: str = Field("idle", pattern="^(focusing|break|idle)$")
    focus_minutes: int = Field(0, ge=0, le=100000)
