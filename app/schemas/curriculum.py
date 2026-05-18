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


class LinkKnowledgePointRequest(BaseModel):
    kp_id: uuid.UUID


class GenerateChapterNoteResponse(BaseModel):
    note_id: uuid.UUID
    status: str

