"""StudySpace 生成式教学 · studyspace_sessions.lesson_plan (JSONB)

知曜开场把「3-5 核心概念框架」写成结构化 lesson_plan 喂前端 PathStepper
（「第 N/M 步」）。结构：{"steps": ["核心概念1", ...], "current_index": int}。
nullable —— 旧会话与 mock_exam 会话无 lesson_plan。

Revision ID: 052
Revises: 051
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "studyspace_sessions",
        sa.Column("lesson_plan", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("studyspace_sessions", "lesson_plan")
