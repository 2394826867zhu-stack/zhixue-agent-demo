"""v0.34 P1-5 · TrainingQuestion.error_reason (错题"错误原因"三分类)

PRD 行 338-340：错误原因维度 = 粗心 / 概念不清 / 方法不会
LLM 在 _grade_answer 时归类 → 影响后续推荐策略。

Revision ID: 032
Revises: 031
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_questions",
        sa.Column("error_reason", sa.String(20), nullable=True),
        # 'careless' | 'concept' | 'method' | NULL（答对时）
    )
    op.create_index("ix_tq_error_reason", "training_questions", ["error_reason"])


def downgrade() -> None:
    op.drop_index("ix_tq_error_reason", "training_questions")
    op.drop_column("training_questions", "error_reason")
