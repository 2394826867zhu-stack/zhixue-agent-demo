"""StudySpace 时间线 enum 补值：ss_timeline_node_kind += spot_quiz_generated

前置 bug：model `TIMELINE_NODE_KIND` 与 schema Literal 已含 `spot_quiz_generated`，
但 PG 枚举类型 `ss_timeline_node_kind`（migration 022 建，仅 8 值）尚未补该值。
故 spot_quiz 工具经 `ss_timeline_service.append_system_node(kind="spot_quiz_generated")`
写节点时，INSERT 在 DB 层因非法 enum 值失败，而 spot_quiz_service 的 `except Exception`
仅 warning 静默吞——随堂练习节点静默不落库。本迁移把该值补进 PG 枚举类型。

坑：PostgreSQL `ALTER TYPE ... ADD VALUE` 不能在事务块里执行（Alembic 默认包事务），
需先 COMMIT 跳出 alembic 事务再 ADD VALUE（autocommit）。`IF NOT EXISTS` 保证幂等
（test DB 走 metadata.create_all 时类型已含该值，本迁移在已含值的库上 no-op）。

Revision ID: 051
Revises: 050
Create Date: 2026-06-21
"""
from alembic import op


revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE 不可在事务块内执行：先提交跳出 alembic 的隐式事务。
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE ss_timeline_node_kind ADD VALUE IF NOT EXISTS 'spot_quiz_generated'"
    )


def downgrade() -> None:
    # PostgreSQL 不支持从枚举类型删除值；无损留下该值（不影响既有数据/约束）。
    pass
