import uuid
from datetime import datetime
from pydantic import BaseModel
from app.schemas.curriculum import CurriculumLessonOut


class StartSessionRequest(BaseModel):
    # 二选一：官方课程章节（结构化内容）或项目树节点（任意学科，AI 据节点+项目上下文开讲）。
    chapter_id: uuid.UUID | None = None
    tree_node_id: uuid.UUID | None = None


class UpdateSessionRequest(BaseModel):
    progress: int | None = None        # 0-100
    agent_session_id: uuid.UUID | None = None
    status: str | None = None          # 'active' | 'paused'


class StudySpaceSessionOut(BaseModel):
    id: uuid.UUID
    chapter_id: uuid.UUID | None        # 树节点会话无 chapter（标题来自节点/项目）
    chapter_title: str
    lesson_title: str
    subject: str
    status: str
    progress: int
    agent_session_id: uuid.UUID | None
    kp_extracted: int
    flashcards_created: int
    stars_earned: int
    lesson_plan: dict | None = None
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
