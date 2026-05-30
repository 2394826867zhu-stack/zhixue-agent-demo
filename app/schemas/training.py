import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


# v0.26 · 题型清单（PRD 行 415-416）
# demo：choice / true_false
# 后续扩展：fill_blank / short_answer / proof / calculation / essay / programming
QuestionType = Literal[
    "choice",         # 选择题
    "true_false",     # 判断题
    "fill_blank",     # 填空
    "short_answer",   # 简答
    "proof",          # 证明
    "calculation",    # 计算
    "essay",          # 写作
    "programming",    # 编程
]


class TrainingStartRequest(BaseModel):
    mode: str
    knowledge_point_id: str | None = None
    subject: str | None = None
    question_count: int = 5

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in ("single_kp", "subject", "compose"):
            raise ValueError("mode 必须为 single_kp / subject / compose")
        return v

    @field_validator("question_count")
    @classmethod
    def valid_count(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("题目数量必须在 1-20 之间")
        return v


# v0.26 · 组卷模式（PRD 9.4 行 645 + 行 415-416）
class ComposeQuizRequest(BaseModel):
    """组卷模式：选题型 / 题量 / 难度 / 范围。

    PRD 9.4 行 645 锁定支持 4 维筛选。
    """
    # 题型清单（任选一个或多个，按比例混合出题）
    question_types: list[QuestionType] = Field(
        default_factory=lambda: ["choice", "true_false"],
        min_length=1, max_length=8,
    )
    question_count: int = Field(default=10, ge=1, le=30)

    # 难度：按知识卡分级（PRD 5.4 蓝/紫/金）
    difficulty_tiers: list[Literal["blue", "purple", "gold"]] = Field(
        default_factory=lambda: ["blue", "purple"],
        min_length=1, max_length=3,
    )

    # 范围（四选一，按优先级解析）
    project_id: uuid.UUID | None = None     # 项目内所有 KP
    tree_node_id: uuid.UUID | None = None   # 项目某子树
    subject: str | None = None              # 学科
    knowledge_point_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    # 可选：StudySpace 会话挂载（写时间线用）
    ss_session_id: uuid.UUID | None = None


class TrainingQuestionOut(BaseModel):
    id: uuid.UUID
    knowledge_point_id: uuid.UUID
    bloom_level: str
    question_type: str
    question: str           # 对应 DB 的 question_text
    reference: str | None   # 对应 DB 的 reference_answer
    user_answer: str | None
    ai_score: int | None
    ai_feedback: str | None
    is_wrong: bool
    answered_at: datetime | None

    @classmethod
    def from_orm(cls, q: object) -> "TrainingQuestionOut":
        return cls(
            id=q.id,
            knowledge_point_id=q.knowledge_point_id,
            bloom_level=q.bloom_level,
            question_type=q.question_type,
            question=q.question_text,
            reference=q.reference_answer,
            user_answer=q.user_answer,
            ai_score=q.ai_score,
            ai_feedback=q.ai_feedback,
            is_wrong=q.is_wrong,
            answered_at=q.answered_at,
        )


class TrainingSessionOut(BaseModel):
    id: uuid.UUID
    mode: str
    subject: str | None
    knowledge_point_id: uuid.UUID | None
    status: str
    question_count: int
    answered_count: int
    avg_score: float | None
    created_at: datetime
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class TrainingSessionDetail(TrainingSessionOut):
    questions: list[TrainingQuestionOut] = []


class AnswerRequest(BaseModel):
    user_answer: str

    @field_validator("user_answer")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("答案不能为空")
        return v.strip()


class AnswerResult(BaseModel):
    question_id: uuid.UUID
    ai_score: int
    ai_feedback: str
    is_wrong: bool
    reference: str          # 对应 DB 的 reference_answer
    session_completed: bool
    session_avg_score: float | None
