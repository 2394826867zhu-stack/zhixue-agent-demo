"""v0.33 P0-1 · Flashcard.first_review_pushed (24h 首次复习推送追踪)

PRD 行 311：学完笔记后 24 小时内自动推送首次闪卡复习（对抗遗忘曲线）

字段：
- first_review_pushed_at — 首次推送时间（NULL = 还没推过 / 推完了不重推）
- 用 created_at 已经能算"创建多久"，无需额外字段记 first_due

Revision ID: 029
Revises: 028
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "flashcards",
        sa.Column("first_review_pushed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_flashcards_first_review_scan",
        "flashcards",
        ["first_review_pushed_at", "review_count", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_flashcards_first_review_scan", "flashcards")
    op.drop_column("flashcards", "first_review_pushed_at")
