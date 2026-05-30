"""项目系统模型 — v2 PRD 学习工作台核心容器

PRD 章节：
- 3.4 我的项目 长条卡 + 拖动排序 + 左滑编辑/删除（行 311-339）
- 项目页：顶部时间线 + 树状路径图（行 379-426）
- 完成度 vs 掌握度 分离（行 408-410）
- 知识卡片来源区分：官方 / 自主（行 539-540）

迁移：alembic 018_v2_projects
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB, ENUM as PgEnum
from app.core.database import Base


# ─────────────────────────────────────────
# 枚举类型 (Postgres ENUM)
# ─────────────────────────────────────────

# 注：create_type=True 允许 tests 的 metadata.create_all 自动建枚举；
# 生产路径走 Alembic 迁移（raw SQL CREATE TYPE），不会冲突。
PROJECT_SOURCE = PgEnum(
    "official", "user_project",
    name="project_source", create_type=True,
)
PROJECT_STATUS = PgEnum(
    "active", "paused", "completed", "archived",
    name="project_status", create_type=True,
)
NODE_DIFFICULTY = PgEnum(
    "blue", "purple", "gold",
    name="node_difficulty", create_type=True,
)
NODE_STATUS = PgEnum(
    "locked", "available", "in_progress", "completed",
    name="node_status", create_type=True,
)
MILESTONE_TYPE = PgEnum(
    "exam", "deadline", "review", "assignment", "custom",
    name="milestone_type", create_type=True,
)


# ─────────────────────────────────────────
# 项目主体
# ─────────────────────────────────────────

class Project(Base):
    """项目 = 用户的学习容器（PRD 3.4 行 311-339）

    可以是官方课程（system_curriculum_id 不空）或自主学习（freeform）。
    Agent 对话式收集字段后通过 from-agent-dialog 端点创建。
    """
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    # 基础信息（PRD 行 327-328：必要类目不能跳过；编辑第一版只允许名/简介 9.1 行 615）
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 来源与归属
    source: Mapped[str] = mapped_column(PROJECT_SOURCE, nullable=False, server_default="user_project")
    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 如果是官方课程派生，关联 curriculum 主章节
    curriculum_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_chapters.id", ondelete="SET NULL"), nullable=True,
    )

    # 状态
    status: Mapped[str] = mapped_column(PROJECT_STATUS, nullable=False, server_default="active")

    # Agent 初始化原始上下文（用户表达 + Agent 整理结果）
    init_context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    # 学习计划参数（PRD 行 328：当前进度/希望完成时间/大事件/每周可投入）
    target_completion_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    weekly_hours: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 完成度（流程推进）vs 掌握度（测验结果）— PRD 行 408-410 必须分离
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mastery_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 排序（PRD 行 319：用户拖动）
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 时间戳
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 关系
    phases: Mapped[list["ProjectPhase"]] = relationship(
        "ProjectPhase", back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectPhase.sort_order",
    )
    milestones: Mapped[list["ProjectMilestone"]] = relationship(
        "ProjectMilestone", back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectMilestone.event_date",
    )
    tree_nodes: Mapped[list["ProjectTreeNode"]] = relationship(
        "ProjectTreeNode", back_populates="project",
        cascade="all, delete-orphan",
    )


# ─────────────────────────────────────────
# 阶段（PRD 行 380-386：阶段节点 = 基础/强化/复习/冲刺）
# ─────────────────────────────────────────

class ProjectPhase(Base):
    """项目阶段（横向时间线的"段"）。"""
    __tablename__ = "project_phases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(60), nullable=False)  # "基础" "强化" 等
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="phases")


# ─────────────────────────────────────────
# 关键事件（PRD 行 382：考试/作业/截止/复习节点）
# ─────────────────────────────────────────

class ProjectMilestone(Base):
    """项目时间线上的关键事件标记。"""
    __tablename__ = "project_milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    milestone_type: Mapped[str] = mapped_column(MILESTONE_TYPE, nullable=False, server_default="custom")

    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 关联考试/任务（可选）
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exams.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="milestones")


# ─────────────────────────────────────────
# 树状路径节点（PRD 行 388-426）
# ─────────────────────────────────────────

class ProjectTreeNode(Base):
    """项目页树状路径的单个节点。

    节点颜色按知识卡难度分级（蓝/紫/金，PRD 行 394）。
    完成度 vs 掌握度 分离（PRD 行 408-410）。
    节点不允许用户手动新增/删除，由 Agent 自动添加（9.1 行 621）。
    """
    __tablename__ = "project_tree_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    # 树状层级
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_tree_nodes.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 关联学习内容
    phase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_phases.id", ondelete="SET NULL"), nullable=True,
    )
    kp_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True,
    )
    curriculum_chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("curriculum_chapters.id", ondelete="SET NULL"), nullable=True,
    )

    # 节点呈现
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty: Mapped[str] = mapped_column(NODE_DIFFICULTY, nullable=False, server_default="blue")
    status: Mapped[str] = mapped_column(NODE_STATUS, nullable=False, server_default="locked")

    # PRD 行 408-410：完成度（学习推进）+ 掌握度（测验结果）
    completion_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mastery_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # 重要性表达（PRD 行 393-396：大小/边框/边缘光 — 数据层只存 weight）
    importance: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1=普通, 2=重点, 3=核心

    # 树布局
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_on_main_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 推荐学习顺序高亮

    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    project: Mapped["Project"] = relationship("Project", back_populates="tree_nodes")
    children: Mapped[list["ProjectTreeNode"]] = relationship(
        "ProjectTreeNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="ProjectTreeNode.sort_order",
    )
    parent: Mapped["ProjectTreeNode | None"] = relationship(
        "ProjectTreeNode", back_populates="children", remote_side="ProjectTreeNode.id",
    )
