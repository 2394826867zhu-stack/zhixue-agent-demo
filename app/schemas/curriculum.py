import uuid
from datetime import datetime
from pydantic import BaseModel


class CurriculumLessonOut(BaseModel):
    id: uuid.UUID
    subject: str
    grade_type: str
    grade_year: int
    semester: int
    chapter_index: int
    chapter_title: str
    lesson_index: int
    lesson_title: str
    textbook_version: str
    is_key: bool
    kp_count: int = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class CurriculumChapterGroup(BaseModel):
    chapter_index: int
    chapter_title: str
    lessons: list[CurriculumLessonOut]


class ChapterDetailLessonOut(BaseModel):
    """同一章节下的兄弟课时（前端 ChapterDetail.lessons 列表项）。"""
    id: uuid.UUID
    title: str
    kp_count: int = 0


class ChapterDetailOut(BaseModel):
    """GET /v1/curriculum/chapters/{id} 详情。字段对齐前端 ChapterDetail：
    title=课时标题(lesson_title) · subject · description=所属章节标题(chapter_title) ·
    kp_count=该用户在此课时下的 KP 数 · has_note=该用户在此课时下是否已有挂笔记的 KP ·
    lessons=同章节兄弟课时（各带该用户 kp_count）。"""
    id: uuid.UUID
    title: str
    subject: str
    kp_count: int
    has_note: bool
    description: str | None = None
    lessons: list[ChapterDetailLessonOut] = []


class LinkKnowledgePointRequest(BaseModel):
    kp_id: uuid.UUID


class GenerateChapterNoteResponse(BaseModel):
    note_id: uuid.UUID
    status: str

