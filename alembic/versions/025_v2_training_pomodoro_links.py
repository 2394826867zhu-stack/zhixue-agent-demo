"""v0.27 · TrainingSession 显式 SS 挂载 + Pomodoro 沉浸挂载

PRD 9.4 行 645 组卷模式 / PRD 6.1 行 372 番茄钟。

Q-05：training_sessions.ss_session_id（前端组卷时显式传 SS）
Q-07：pomodoro_records.immersion_session_id（沉浸期间的番茄钟可 join 汇总）

Revision ID: 025
Revises: 024
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # training_sessions.ss_session_id
    op.add_column(
        "training_sessions",
        sa.Column(
            "ss_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("studyspace_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_training_sessions_ss_session_id", "training_sessions", ["ss_session_id"])

    # pomodoro_records.immersion_session_id
    op.add_column(
        "pomodoro_records",
        sa.Column(
            "immersion_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("immersion_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_pomodoro_records_immersion_session_id",
        "pomodoro_records",
        ["immersion_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pomodoro_records_immersion_session_id", "pomodoro_records")
    op.drop_column("pomodoro_records", "immersion_session_id")
    op.drop_index("ix_training_sessions_ss_session_id", "training_sessions")
    op.drop_column("training_sessions", "ss_session_id")
