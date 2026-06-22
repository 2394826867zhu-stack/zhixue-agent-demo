"""P0-1 · 每日签到唯一去重：check_ins.checkin_date + uq(user_id, checkin_date)

上线前审计发现签到无每日去重 → 一天连点 N 次发 20×N 知星刷爆经济系统。
本迁移加去重键并清理漏洞期产生的重复签到（每组保留最早一条）。

expand-contract：先加 nullable 列回填 → 去重 → 收紧 NOT NULL → 唯一约束。

Revision ID: 053
Revises: 052
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op


revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 加列（先 nullable 以便回填存量）
    op.add_column("check_ins", sa.Column("checkin_date", sa.Date(), nullable=True))

    # 2. 回填：按北京时区(UTC+8)把 created_at 归一到"当日"
    op.execute(
        "UPDATE check_ins "
        "SET checkin_date = (created_at AT TIME ZONE 'Asia/Shanghai')::date "
        "WHERE checkin_date IS NULL"
    )

    # 3. 去重：同一 (user_id, checkin_date) 只保留最早一条（清理漏洞期重复签到）
    op.execute(
        """
        DELETE FROM check_ins c
        USING check_ins d
        WHERE c.user_id = d.user_id
          AND c.checkin_date = d.checkin_date
          AND c.created_at > d.created_at
        """
    )
    # created_at 完全相同的极端并发残留用 id 兜底
    op.execute(
        """
        DELETE FROM check_ins c
        USING check_ins d
        WHERE c.user_id = d.user_id
          AND c.checkin_date = d.checkin_date
          AND c.created_at = d.created_at
          AND c.id > d.id
        """
    )

    # 4. 收紧 NOT NULL
    op.alter_column("check_ins", "checkin_date", nullable=False)

    # 5. 索引 + 唯一约束
    op.create_index("ix_check_ins_checkin_date", "check_ins", ["checkin_date"])
    op.create_unique_constraint(
        "uq_checkin_user_date", "check_ins", ["user_id", "checkin_date"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_checkin_user_date", "check_ins", type_="unique")
    op.drop_index("ix_check_ins_checkin_date", table_name="check_ins")
    op.drop_column("check_ins", "checkin_date")
