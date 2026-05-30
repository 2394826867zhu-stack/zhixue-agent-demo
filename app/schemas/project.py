"""项目系统 Pydantic Schemas — v2 PRD"""
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────
# Tree Node
# ─────────────────────────────────────────

class TreeNodeOut(BaseModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    depth: int
    phase_id: uuid.UUID | None
    kp_id: uuid.UUID | None
    curriculum_chapter_id: uuid.UUID | None
    title: str
    difficulty: Literal["blue", "purple", "gold"]
    status: Literal["locked", "available", "in_progress", "completed"]
    completion_pct: float
    mastery_pct: float
    importance: int
    sort_order: int
    is_on_main_path: bool
    last_studied_at: datetime | None
    completed_at: datetime | None
    model_config = {"from_attributes": True}


class TreeNodeBubble(BaseModel):
    """节点点击气泡（PRD 行 402-410）— 开始学习/直接测验。"""
    node: TreeNodeOut
    course_title: str
    course_description: str
    can_start_study: bool = True
    can_start_quiz: bool = True


# ─────────────────────────────────────────
# Phase / Milestone
# ─────────────────────────────────────────

class PhaseOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    start_date: datetime | None
    end_date: datetime | None
    sort_order: int
    is_current: bool
    completion_pct: float
    model_config = {"from_attributes": True}


class MilestoneOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    milestone_type: Literal["exam", "deadline", "review", "assignment", "custom"]
    event_date: datetime
    is_completed: bool
    exam_id: uuid.UUID | None
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
# Project Create / Update
# ─────────────────────────────────────────

class ProjectCreate(BaseModel):
    """直接创建（用于已有结构化数据的场景）。
    PRD 行 327-339：必要类目不能跳过。
    """
    name: str = Field(min_length=1, max_length=120)
    summary: str = ""
    source: Literal["official", "user_project"] = "user_project"
    subject: str | None = None
    curriculum_chapter_id: uuid.UUID | None = None
    target_completion_date: datetime | None = None
    weekly_hours: float | None = None


class ProjectUpdate(BaseModel):
    """编辑项目 — PRD 9.1 行 615：第一版只允许修改名+简介。"""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=1000)


class ProjectReorderItem(BaseModel):
    project_id: uuid.UUID
    sort_order: int


class ProjectReorderRequest(BaseModel):
    items: list[ProjectReorderItem]


# ─────────────────────────────────────────
# Agent 对话式创建（PRD 行 330-339）
# ─────────────────────────────────────────

class ProjectInitDraft(BaseModel):
    """Agent 与用户对话整理出的项目骨架。

    PRD 9.2 行 626-628：必要类目不能跳过；次要类目可跳过。
    PRD 行 628：创建一开始必须问清楚 — 用户自己创建 vs Agent 查找信息后生成。
    """
    name: str
    summary: str
    subject: str | None = None
    init_context: dict = {}
    target_completion_date: datetime | None = None
    weekly_hours: float | None = None
    create_mode: Literal["user", "agent_assisted"] = "agent_assisted"


class ProjectPreviewCard(BaseModel):
    """项目生成前的结构化预览卡 — PRD 行 333-337。

    用户确认前必须看到：基础信息 + Agent 将生成内容 + 时间线预览 + 树状架构预览。
    """
    draft: ProjectInitDraft
    proposed_phases: list[dict]       # [{ name, description, est_weeks }]
    proposed_milestones: list[dict]   # [{ title, type, days_from_now }]
    proposed_tree_summary: dict       # { total_nodes, blue_count, purple_count, gold_count }
    estimated_total_hours: float


class ProjectConfirmRequest(BaseModel):
    """用户确认 preview card 后正式生成项目。"""
    preview: ProjectPreviewCard


# ─────────────────────────────────────────
# Project Out（列表 / 详情）
# ─────────────────────────────────────────

class PhaseSummaryItem(BaseModel):
    """列表卡轻量阶段摘要 — 仅 name / is_current / completion_pct。"""
    name: str
    is_current: bool
    completion_pct: float
    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: uuid.UUID
    name: str
    summary: str
    source: Literal["official", "user_project"]
    subject: str | None
    status: Literal["active", "paused", "completed", "archived"]
    completion_pct: float
    mastery_pct: float
    sort_order: int
    target_completion_date: datetime | None
    started_at: datetime | None
    updated_at: datetime
    # 阶段摘要 + milestone 数量（SCREENS_INVENTORY 2.1）
    phases: list[PhaseSummaryItem] = []
    milestone_count: int = 0
    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectListItem]
    total: int
    page: int = 1
    page_size: int = 100


class ProjectDetail(BaseModel):
    """项目详情 = 主体 + 时间线 + 树状路径概要。"""
    id: uuid.UUID
    name: str
    summary: str
    source: Literal["official", "user_project"]
    subject: str | None
    status: Literal["active", "paused", "completed", "archived"]
    completion_pct: float
    mastery_pct: float
    init_context: dict
    target_completion_date: datetime | None
    weekly_hours: float | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # 时间线（PRD 行 379-386）
    phases: list[PhaseOut] = []
    milestones: list[MilestoneOut] = []
    current_phase_id: uuid.UUID | None = None

    # 树概要（详细树通过 /tree 单独端点拉取，避免列表过大）
    tree_node_count: int = 0
    tree_completed_count: int = 0

    model_config = {"from_attributes": True}


class ProjectDataSummary(BaseModel):
    """项目页底部数据栏环状图汇总（PRD 行 410）。"""
    completion_pct: float
    mastery_pct: float
    tree_nodes_total: int
    tree_nodes_completed: int
    flashcards_total: int
    flashcards_due: int
    mistakes_total: int
    notes_total: int
    study_minutes: int
