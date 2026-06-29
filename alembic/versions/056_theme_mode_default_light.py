"""users.theme_mode 默认 auto → light（新用户浅色优先，修深色默认 bug）

审计(2026-06-29)：新用户默认 theme_mode='auto' → 前端跟随系统，在深色系统设备上
进 app 即深色，与「产品定位浅色为主」(ThemeModeProvider 初值 light)矛盾，用户需进
偏好设置手动切一下才正常。改 server_default='light'：仅影响**新建用户**，存量用户
保留各自现值（不擅改其已有选择，且 auto/dark 可能是其主动设定）。

Revision ID: 056
Revises: 055
Create Date: 2026-06-29
"""
from alembic import op


revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 仅改列默认值（影响今后 INSERT 的缺省），不回填存量行。
    op.alter_column("users", "theme_mode", server_default="light")


def downgrade() -> None:
    op.alter_column("users", "theme_mode", server_default="auto")
