"""v0.29 Memory · agent_episodes (跨 session 事件记忆)

PRD 行 25 落地：Agent 记着用户什么时候开始拖延、哪一章老出错、考试前几天状态。

Q4 锁定：agent_memory 主动 save_memory（用户画像）
Q5 锁定：行为信号自动写入 episodes（6 类事件 hook）
Q6 锁定：90 天保留，importance≥7 永久

Revision ID: 027
Revises: 026
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),

        # 事件分类
        sa.Column("event_kind", sa.String(40), nullable=False),
        # kp_struggle / inactive_streak / exam_approaching / streak_milestone /
        # phase_completed / ss_completed / schedule_shift / agent_observation

        # 摘要（用于召回 + 显示）
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("detail", JSONB, server_default=sa.text("'{}'::jsonb")),

        # 引用实体
        sa.Column("ref_kp_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("ref_note_ids", ARRAY(UUID(as_uuid=True)), nullable=True),
        sa.Column("ref_project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),

        # 重要性 + 情绪
        sa.Column("importance", sa.SmallInteger, nullable=False, server_default="5"),  # 0-10
        sa.Column("emotional_tone", sa.String(20), nullable=True),  # positive / negative / neutral

        # 关联到 document_embeddings（向量化 summary 用于召回）
        sa.Column("embedding_id", UUID(as_uuid=True), nullable=True),

        sa.Column("occurred_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_episodes_user", "agent_episodes", ["user_id"])
    op.create_index("ix_agent_episodes_kind", "agent_episodes", ["event_kind"])
    op.create_index("ix_agent_episodes_user_occurred", "agent_episodes", ["user_id", "occurred_at"])
    op.create_index("ix_agent_episodes_importance", "agent_episodes", ["user_id", "importance"])


def downgrade() -> None:
    op.drop_index("ix_agent_episodes_importance", "agent_episodes")
    op.drop_index("ix_agent_episodes_user_occurred", "agent_episodes")
    op.drop_index("ix_agent_episodes_kind", "agent_episodes")
    op.drop_index("ix_agent_episodes_user", "agent_episodes")
    op.drop_table("agent_episodes")
