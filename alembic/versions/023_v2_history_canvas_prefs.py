"""v2 PRD · Agent 对话记录 + StudySpace 画板 + 用户 UI 偏好

PRD 章节：
- 9.7 行 669 控制台浏览记录
- 9.7 行 673 控制台对话搜索
- 9.3 行 636 StudySpace 保留画板 / 手写区
- 9.11 行 702 暗色模式

Revision ID: 023
Revises: 022
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_conversation_logs（PRD 9.7）────────────────────
    op.create_table(
        "agent_conversation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("last_message_preview", sa.Text, nullable=True),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("search_blob", sa.Text, nullable=False, server_default=""),
        sa.Column("tools_called", JSONB, nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_agent_conv_logs_user_id", "agent_conversation_logs", ["user_id"])
    op.create_index("ix_agent_conv_logs_session_id", "agent_conversation_logs", ["session_id"])
    op.create_index("ix_agent_conv_logs_user_activity", "agent_conversation_logs", ["user_id", "last_activity_at"])
    # ILIKE 走顺序扫描即可，体量小；若上规模再加 pg_trgm GIN
    op.create_index("ix_agent_conv_logs_search", "agent_conversation_logs", ["user_id", "title"])

    # ── ss_canvas_strokes（PRD 9.3）──────────────────────────
    op.create_table(
        "ss_canvas_strokes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", UUID(as_uuid=True),
            sa.ForeignKey("studyspace_sessions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path_d", sa.Text, nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="#1F2937"),
        sa.Column("stroke_width", sa.Float, nullable=False, server_default="2.0"),
        sa.Column("opacity", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("page_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_ss_canvas_strokes_session_id", "ss_canvas_strokes", ["session_id"])
    op.create_index(
        "ix_ss_canvas_strokes_session_page_sort",
        "ss_canvas_strokes",
        ["session_id", "page_index", "sort_order"],
    )

    # ── users · UI 偏好（PRD 9.11）───────────────────────────
    op.add_column("users", sa.Column("theme_mode", sa.String(10), nullable=False, server_default="auto"))
    op.add_column("users", sa.Column("dynamic_type_scale", sa.Float, nullable=False, server_default="1.0"))
    op.add_column("users", sa.Column("reduced_motion", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("haptics_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("users", "haptics_enabled")
    op.drop_column("users", "reduced_motion")
    op.drop_column("users", "dynamic_type_scale")
    op.drop_column("users", "theme_mode")

    op.drop_index("ix_ss_canvas_strokes_session_page_sort", "ss_canvas_strokes")
    op.drop_index("ix_ss_canvas_strokes_session_id", "ss_canvas_strokes")
    op.drop_table("ss_canvas_strokes")

    op.drop_index("ix_agent_conv_logs_search", "agent_conversation_logs")
    op.drop_index("ix_agent_conv_logs_user_activity", "agent_conversation_logs")
    op.drop_index("ix_agent_conv_logs_session_id", "agent_conversation_logs")
    op.drop_index("ix_agent_conv_logs_user_id", "agent_conversation_logs")
    op.drop_table("agent_conversation_logs")
