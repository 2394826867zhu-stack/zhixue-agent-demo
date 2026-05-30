"""v2 PRD · StudySpace 垂直时间线节点

PRD 行 436-448：沉淀学习内容/KP/闪卡/训练/错题/复盘/Agent 对话痕迹

Revision ID: 022
Revises: 021
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


ss_timeline_node_kind_enum = postgresql.ENUM(
    "content", "kp_extracted", "flashcard_result", "training_result",
    "mistake", "reflection", "agent_message", "agent_action",
    name="ss_timeline_node_kind", create_type=False,
)


def upgrade() -> None:
    op.execute(
        "CREATE TYPE ss_timeline_node_kind AS ENUM ("
        "'content','kp_extracted','flashcard_result','training_result',"
        "'mistake','reflection','agent_message','agent_action')"
    )

    op.create_table(
        "studyspace_timeline_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id", UUID(as_uuid=True),
            sa.ForeignKey("studyspace_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", ss_timeline_node_kind_enum, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "ref_kp_id", UUID(as_uuid=True),
            sa.ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "ref_flashcard_id", UUID(as_uuid=True),
            sa.ForeignKey("flashcards.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "ref_training_question_id", UUID(as_uuid=True),
            sa.ForeignKey("training_questions.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "ref_note_id", UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_editable", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "amends_node_id", UUID(as_uuid=True),
            sa.ForeignKey("studyspace_timeline_nodes.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_ss_timeline_session_id", "studyspace_timeline_nodes", ["session_id"])
    op.create_index("ix_ss_timeline_user_id", "studyspace_timeline_nodes", ["user_id"])
    op.create_index(
        "ix_ss_timeline_session_sort",
        "studyspace_timeline_nodes",
        ["session_id", "sort_order", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ss_timeline_session_sort", "studyspace_timeline_nodes")
    op.drop_index("ix_ss_timeline_user_id", "studyspace_timeline_nodes")
    op.drop_index("ix_ss_timeline_session_id", "studyspace_timeline_nodes")
    op.drop_table("studyspace_timeline_nodes")
    op.execute("DROP TYPE IF EXISTS ss_timeline_node_kind")
