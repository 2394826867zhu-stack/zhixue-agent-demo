"""Add app_config singleton table for A-14 remote config + C-22 announcements."""
from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feature_flags", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("min_app_version", sa.String(20), nullable=True),
        sa.Column("announcement", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # 单例默认行（id=1，空配置），后续 admin PATCH 这一行
    op.execute("INSERT INTO app_config (id, feature_flags) VALUES (1, '{}')")


def downgrade() -> None:
    op.drop_table("app_config")
