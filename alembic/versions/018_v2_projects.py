"""v2 PRD · 项目系统 + 时间线 + 树状路径

PRD 章节:
- 3.4 我的项目（行 311-339）
- 项目页时间线 + 树状路径（行 379-426）
- 完成度 vs 掌握度 分离（行 408-410）
- 知识卡蓝/紫/金 分级（5.4 行 528-541）

Revision ID: 018
Revises: 017
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


# Reference enums (create_type=False so columns just reference)
project_source_enum = postgresql.ENUM("official", "user_project", name="project_source", create_type=False)
project_status_enum = postgresql.ENUM("active", "paused", "completed", "archived", name="project_status", create_type=False)
node_difficulty_enum = postgresql.ENUM("blue", "purple", "gold", name="node_difficulty", create_type=False)
node_status_enum = postgresql.ENUM("locked", "available", "in_progress", "completed", name="node_status", create_type=False)
milestone_type_enum = postgresql.ENUM(
    "exam", "deadline", "review", "assignment", "custom",
    name="milestone_type", create_type=False,
)


def upgrade() -> None:
    # ── enum types (raw SQL, idempotent) ────────────────────────────
    op.execute("CREATE TYPE project_source AS ENUM ('official', 'user_project')")
    op.execute("CREATE TYPE project_status AS ENUM ('active', 'paused', 'completed', 'archived')")
    op.execute("CREATE TYPE node_difficulty AS ENUM ('blue', 'purple', 'gold')")
    op.execute("CREATE TYPE node_status AS ENUM ('locked', 'available', 'in_progress', 'completed')")
    op.execute("CREATE TYPE milestone_type AS ENUM ('exam', 'deadline', 'review', 'assignment', 'custom')")

    # ── projects ─────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("source", project_source_enum, nullable=False, server_default="user_project"),
        sa.Column("subject", sa.String(50), nullable=True),
        sa.Column(
            "curriculum_chapter_id",
            UUID(as_uuid=True),
            sa.ForeignKey("curriculum_chapters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", project_status_enum, nullable=False, server_default="active"),
        sa.Column("init_context", JSONB, nullable=False, server_default="{}"),
        sa.Column("target_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weekly_hours", sa.Float, nullable=True),
        sa.Column("completion_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("mastery_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_user_sort", "projects", ["user_id", "sort_order"])
    op.create_index("ix_projects_user_status", "projects", ["user_id", "status"])

    # ── project_phases ───────────────────────────────────────
    op.create_table(
        "project_phases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("completion_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_project_phases_project_id", "project_phases", ["project_id"])

    # ── project_milestones ───────────────────────────────────
    op.create_table(
        "project_milestones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("milestone_type", milestone_type_enum, nullable=False, server_default="custom"),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_completed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("exam_id", UUID(as_uuid=True), sa.ForeignKey("exams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_project_milestones_project_id", "project_milestones", ["project_id"])
    op.create_index("ix_project_milestones_event_date", "project_milestones", ["event_date"])

    # ── project_tree_nodes ───────────────────────────────────
    op.create_table(
        "project_tree_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("project_tree_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("phase_id", UUID(as_uuid=True), sa.ForeignKey("project_phases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kp_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("curriculum_chapter_id", UUID(as_uuid=True), sa.ForeignKey("curriculum_chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("difficulty", node_difficulty_enum, nullable=False, server_default="blue"),
        sa.Column("status", node_status_enum, nullable=False, server_default="locked"),
        sa.Column("completion_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("mastery_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("importance", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_on_main_path", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_studied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_project_tree_nodes_project_id", "project_tree_nodes", ["project_id"])
    op.create_index("ix_project_tree_nodes_parent_id", "project_tree_nodes", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_project_tree_nodes_parent_id", "project_tree_nodes")
    op.drop_index("ix_project_tree_nodes_project_id", "project_tree_nodes")
    op.drop_table("project_tree_nodes")

    op.drop_index("ix_project_milestones_event_date", "project_milestones")
    op.drop_index("ix_project_milestones_project_id", "project_milestones")
    op.drop_table("project_milestones")

    op.drop_index("ix_project_phases_project_id", "project_phases")
    op.drop_table("project_phases")

    op.drop_index("ix_projects_user_status", "projects")
    op.drop_index("ix_projects_user_sort", "projects")
    op.drop_index("ix_projects_user_id", "projects")
    op.drop_table("projects")

    op.execute("DROP TYPE IF EXISTS milestone_type")
    op.execute("DROP TYPE IF EXISTS node_status")
    op.execute("DROP TYPE IF EXISTS node_difficulty")
    op.execute("DROP TYPE IF EXISTS project_status")
    op.execute("DROP TYPE IF EXISTS project_source")
