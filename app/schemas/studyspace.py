import uuid
from datetime import datetime
from pydantic import BaseModel
from app.schemas.curriculum import CurriculumLessonOut


class StartSessionRequest(BaseModel):
    chapter_id: uuid.UUID


class UpdateSessionRequest(BaseModel):
    progress: int | None = None        # 0-100
    agent_session_id: uuid.UUID | None = None
    status: str | None = None          # 'active' | 'paused'


class StudySpaceSessionOut(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID
    chapter_title: str
    lesson_title: str
    subject: str
    status: str
    progress: int
    agent_session_id: uuid.UUID | None
    kp_extracted: int
    flashcards_created: int
    stars_earned: int
    started_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class CompleteSessionResponse(BaseModel):
    session_id: uuid.UUID
    kp_extracted: int
    flashcards_created: int
    stars_earned: int
    next_lesson: CurriculumLessonOut | None


class LessonProgress(BaseModel):
    chapter_id: uuid.UUID
    status: str    # 'locked' | 'available' | 'in_progress' | 'completed'
    progress_pct: int
    last_session_at: datetime | None
