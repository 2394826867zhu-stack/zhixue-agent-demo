"""项目创建体系 v3 · projects 三阶漏斗 intake 字段 + subject 扩容

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md（INC-A）
全部 add_column 带 server_default → 存量项目零破坏向后兼容
（goal_type=interest / starting_mode=from_scratch / scope_mode=full_subject）。
subject String(50)→String(80)（两层分类格式 "{category} > {subject}"）。
expand-only，downgrade 可逆（drop 新列 + subject 回 50）。

Revision ID: 055
Revises: 054
Create Date: 2026-06-25
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 第一层 · 为什么学
    op.add_column("projects", sa.Column(
        "goal_type", sa.String(length=20), nullable=False, server_default="interest"))
    op.add_column("projects", sa.Column(
        "goal_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    # 第二层 · 从哪开始
    op.add_column("projects", sa.Column(
        "starting_mode", sa.String(length=20), nullable=False, server_default="from_scratch"))
    op.add_column("projects", sa.Column(
        "starting_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"))
    op.add_column("projects", sa.Column(
        "prior_knowledge_strategy", sa.String(length=10), nullable=True))
    # 第三层 · 怎么学
    op.add_column("projects", sa.Column(
        "mastery_depth", sa.String(length=10), nullable=True))
    op.add_column("projects", sa.Column(
        "scope_mode", sa.String(length=20), nullable=False, server_default="full_subject"))
    op.add_column("projects", sa.Column(
        "scope_topics", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"))
    # subject 扩容 50 → 80（两层分类格式 "{category} > {subject}"）
    op.alter_column("projects", "subject",
                    type_=sa.String(length=80), existing_type=sa.String(length=50),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column("projects", "subject",
                    type_=sa.String(length=50), existing_type=sa.String(length=80),
                    existing_nullable=True)
    op.drop_column("projects", "scope_topics")
    op.drop_column("projects", "scope_mode")
    op.drop_column("projects", "mastery_depth")
    op.drop_column("projects", "prior_knowledge_strategy")
    op.drop_column("projects", "starting_payload")
    op.drop_column("projects", "starting_mode")
    op.drop_column("projects", "goal_spec")
    op.drop_column("projects", "goal_type")
