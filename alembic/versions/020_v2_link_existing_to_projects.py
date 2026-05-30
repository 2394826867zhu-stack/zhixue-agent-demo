"""v2 PRD · 现有表挂载到项目系统

PRD 5.4 行 528-541 蓝/紫/金 + 官方/自主区分
PRD 6.1 行 372 沉浸番茄钟自定义循环

为现有核心表加入 v2 链接字段：
  notes / knowledge_points / flashcards / training_questions
  studyspace_sessions / pomodoro_records / guidance_sessions
  → project_id（挂载）+ notebook_origin（官方/自主）
  → knowledge_points 额外加 difficulty_tier（蓝/紫/金）
  → pomodoro 加自定义番茄钟控制字段

Revision ID: 020
Revises: 019
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


# 复用 018 已创建的 ENUM 类型
project_source_enum = postgresql.ENUM("official", "user_project", name="project_source", create_type=False)
node_difficulty_enum = postgresql.ENUM("blue", "purple", "gold", name="node_difficulty", create_type=False)


def _add_project_id(table: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(f"ix_{table}_project_id", table, ["project_id"])


def _add_notebook_origin(table: str) -> None:
    op.add_column(
        table,
        sa.Column(
            "notebook_origin",
            project_source_enum,
            nullable=False,
            server_default="user_project",
        ),
    )


def upgrade() -> None:
    # ── notes ────────────────────────────────────────────────
    _add_project_id("notes")
    _add_notebook_origin("notes")
    op.add_column(
        "notes",
        sa.Column("is_editable", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    # ── knowledge_points ─────────────────────────────────────
    _add_project_id("knowledge_points")
    _add_notebook_origin("knowledge_points")
    op.add_column(
        "knowledge_points",
        sa.Column(
            "difficulty_tier",
            node_difficulty_enum,
            nullable=False,
            server_default="blue",
        ),
    )
    op.create_index("ix_knowledge_points_difficulty_tier", "knowledge_points", ["difficulty_tier"])

    # ── flashcards ───────────────────────────────────────────
    _add_project_id("flashcards")
    _add_notebook_origin("flashcards")

    # ── training_questions（错题归口此表）────────────────────
    _add_project_id("training_questions")
    _add_notebook_origin("training_questions")

    # ── studyspace_sessions ──────────────────────────────────
    _add_project_id("studyspace_sessions")
    op.add_column(
        "studyspace_sessions",
        sa.Column(
            "tree_node_id",
            UUID(as_uuid=True),
            sa.ForeignKey("project_tree_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ── pomodoro_records · 自定义番茄钟（PRD 6.1 行 372）────
    op.add_column(
        "pomodoro_records",
        sa.Column("focus_minutes", sa.Integer, nullable=False, server_default="25"),
    )
    op.add_column(
        "pomodoro_records",
        sa.Column("break_minutes", sa.Integer, nullable=False, server_default="5"),
    )
    op.add_column(
        "pomodoro_records",
        sa.Column("long_break_minutes", sa.Integer, nullable=False, server_default="15"),
    )
    op.add_column(
        "pomodoro_records",
        sa.Column("cycle_count", sa.Integer, nullable=False, server_default="4"),
    )

    # ── guidance_sessions（苏格拉底引导也可绑项目）──────────
    _add_project_id("guidance_sessions")


def downgrade() -> None:
    op.drop_index("ix_guidance_sessions_project_id", "guidance_sessions")
    op.drop_column("guidance_sessions", "project_id")

    for col in ("cycle_count", "long_break_minutes", "break_minutes", "focus_minutes"):
        op.drop_column("pomodoro_records", col)

    op.drop_column("studyspace_sessions", "tree_node_id")
    op.drop_index("ix_studyspace_sessions_project_id", "studyspace_sessions")
    op.drop_column("studyspace_sessions", "project_id")

    op.drop_index("ix_training_questions_project_id", "training_questions")
    op.drop_column("training_questions", "notebook_origin")
    op.drop_column("training_questions", "project_id")

    op.drop_index("ix_flashcards_project_id", "flashcards")
    op.drop_column("flashcards", "notebook_origin")
    op.drop_column("flashcards", "project_id")

    op.drop_index("ix_knowledge_points_difficulty_tier", "knowledge_points")
    op.drop_column("knowledge_points", "difficulty_tier")
    op.drop_column("knowledge_points", "notebook_origin")
    op.drop_index("ix_knowledge_points_project_id", "knowledge_points")
    op.drop_column("knowledge_points", "project_id")

    op.drop_column("notes", "is_editable")
    op.drop_column("notes", "notebook_origin")
    op.drop_index("ix_notes_project_id", "notes")
    op.drop_column("notes", "project_id")
