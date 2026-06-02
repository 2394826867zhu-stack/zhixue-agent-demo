"""修复漂移：幂等确保 subscription_events 表存在（E-01/E-04 依赖）。

背景：migration 042 曾 stamp 041（标记已应用但未执行其 DDL），导致经此路径建立的库
缺失 subscription_events 表。E-01 RevenueCat webhook 与 E-04 试用都会向该表写审计事件，
缺表则 500。本迁移在表缺失时按 041 的定义补建（含索引），表已存在则为 no-op，
对健康库无副作用、对漂移库自愈。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "subscription_events" in insp.get_table_names():
        return  # 健康库：表已存在，no-op

    op.create_table(
        "subscription_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revenuecat_event_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscription_events_user_id", "subscription_events", ["user_id"])
    op.create_index(
        "ix_subscription_events_revenuecat_event_id",
        "subscription_events", ["revenuecat_event_id"], unique=True,
    )


def downgrade() -> None:
    # 自愈迁移不在 downgrade 删表（避免误删健康库既有数据）；
    # 表归属仍由 041 负责，此处留空。
    pass
