import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, field_validator


class NoteGenerateRequest(BaseModel):
    """主入口：AI主动生成"""
    topic: str
    subject: str | None = None

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("主题不能为空")
        if len(v) > 200:
            raise ValueError("主题描述不能超过200字")
        return v.strip()


class NoteUploadRequest(BaseModel):
    """次入口：用户上传文字"""
    content: str
    title: str | None = None
    subject: str | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("内容不能为空")
        return v.strip()


class KnowledgePointBrief(BaseModel):
    id: uuid.UUID
    name: str
    bloom_level: str
    mastery_status: str
    model_config = {"from_attributes": True}


class NoteResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    subject: str | None
    source_type: str
    status: str
    full_version: str | None
    exam_version: str | None
    graph_mermaid: str | None
    difficulty_points: list
    flashcards_generated: bool
    knowledge_points: list[KnowledgePointBrief] = []
    created_at: datetime
    model_config = {"from_attributes": True}


class NoteBrief(BaseModel):
    """笔记列表用，不含三件套正文"""
    id: uuid.UUID
    title: str | None
    subject: str | None
    source_type: str
    status: str
    flashcards_generated: bool
    kp_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class NoteTaskStatus(BaseModel):
    note_id: uuid.UUID
    status: str          # processing | done | failed
    progress: int        # 0-100
    message: str


class NoteCreateResult(BaseModel):
    """generate / upload 三入口的返回（笔记异步生成已入队）。"""
    note_id: str
    status: str          # processing


class NoteListResponse(BaseModel):
    """笔记列表（无 total，分组前端按需加载）。"""
    items: list[NoteBrief]
    page: int
    page_size: int


class NoteFlashcardGenResult(BaseModel):
    created: int
    knowledge_points: int
    skipped: bool = False
