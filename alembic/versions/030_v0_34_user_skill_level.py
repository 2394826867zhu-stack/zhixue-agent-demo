"""v0.34 P1-2 · user_skill_levels 表 (自适应难度)

按用户 × 学科存当前 bloom_level，配合训练正确率动态调整。

升降级规则：
- 连续 3 题正确 → 升一级
- 连续 2 题错误 → 降一级
- 启动值：remember

bloom 阶梯：remember → understand → apply → analyze → evaluate → create

Revision ID: 030
Revises: 029
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_skill_levels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(50), nullable=False),
        sa.Column("current_bloom", sa.String(20), nullable=False, server_default="remember"),
        sa.Column("consecutive_correct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_wrong", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_correct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "subject", name="uq_user_skill_subject"),
    )
    op.create_index("ix_user_skill_user", "user_skill_levels", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_skill_user", "user_skill_levels")
    op.drop_table("user_skill_levels")
