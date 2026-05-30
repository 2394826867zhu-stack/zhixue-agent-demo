"""v0.34 P1-4 · feynman_attempts 表 (费曼输出 + AI 评估)

PRD 行 372-379：学完一个知识点后系统提示
"请用最简单的语言，向一个完全不懂的人解释这个概念。"
AI 评估解释的准确性，指出理解漏洞，引导补充。

评分维度（用户决策锁定）：
- 准确性 40%
- 完整性 30%
- 清晰度 30%

Revision ID: 031
Revises: 030
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feynman_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kp_id", UUID(as_uuid=True),
                  sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ss_session_id", UUID(as_uuid=True),
                  sa.ForeignKey("studyspace_sessions.id", ondelete="SET NULL"), nullable=True),

        # 用户输入
        sa.Column("user_explanation", sa.Text, nullable=False),

        # AI 评估
        sa.Column("accuracy_score", sa.SmallInteger, nullable=True),    # 0-100
        sa.Column("completeness_score", sa.SmallInteger, nullable=True),
        sa.Column("clarity_score", sa.SmallInteger, nullable=True),
        sa.Column("total_score", sa.SmallInteger, nullable=True),  # 40*A + 30*C + 30*Cl 加权
        sa.Column("gaps", JSONB, server_default=sa.text("'[]'::jsonb")),  # 漏洞列表
        sa.Column("ai_feedback", sa.Text, nullable=True),  # 综合反馈
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending / graded / failed

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_feynman_user", "feynman_attempts", ["user_id"])
    op.create_index("ix_feynman_kp", "feynman_attempts", ["kp_id"])
    op.create_index("ix_feynman_user_kp", "feynman_attempts", ["user_id", "kp_id"])


def downgrade() -> None:
    op.drop_index("ix_feynman_user_kp", "feynman_attempts")
    op.drop_index("ix_feynman_kp", "feynman_attempts")
    op.drop_index("ix_feynman_user", "feynman_attempts")
    op.drop_table("feynman_attempts")
