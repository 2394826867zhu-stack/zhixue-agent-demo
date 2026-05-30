"""v0.30 Reasoning · agent_tool_traces (可观测性)

PRD Agent OS L7 Eval & Observability。
跟踪每次工具调用的 latency / status / tokens / 用户后续是否撤销追加修正。

Revision ID: 028
Revises: 027
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),  # 关联用户上一条消息

        sa.Column("tool_name", sa.String(60), nullable=False),
        sa.Column("arguments", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_summary", sa.Text, nullable=True),  # 截断 1000 字

        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),

        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        # success / error / timeout
        sa.Column("error_message", sa.Text, nullable=True),

        sa.Column("tokens_in", sa.Integer, nullable=True),
        sa.Column("tokens_out", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),

        # 用户后续反馈
        sa.Column("was_helpful", sa.Boolean, nullable=True),  # NULL = 未反馈
        sa.Column("user_action", sa.String(20), nullable=True),
        # regenerate / correct / undo / continue / null

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tool_traces_user", "agent_tool_traces", ["user_id"])
    op.create_index("ix_tool_traces_tool", "agent_tool_traces", ["tool_name"])
    op.create_index("ix_tool_traces_session", "agent_tool_traces", ["session_id"])
    op.create_index("ix_tool_traces_latency", "agent_tool_traces", ["latency_ms"])
    op.create_index("ix_tool_traces_created", "agent_tool_traces", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tool_traces_created", "agent_tool_traces")
    op.drop_index("ix_tool_traces_latency", "agent_tool_traces")
    op.drop_index("ix_tool_traces_session", "agent_tool_traces")
    op.drop_index("ix_tool_traces_tool", "agent_tool_traces")
    op.drop_index("ix_tool_traces_user", "agent_tool_traces")
    op.drop_table("agent_tool_traces")
