"""审计 L6 · 清理老架构孤儿对象（库里有、模型没了 → alembic check 漂移）

迁移 016 建的 3 个对象在后续迭代中被取代/废弃，但从未写 drop 迁移，致 model↔迁移漂移：
- uploaded_files 表：被 D-06 知识库 kb_files（迁移 040）+ /v1/files 端点取代，无 ORM 模型、零代码引用。
- training_sessions.studyspace_session_id 列：v0.27（迁移 025）改用 ss_session_id；模型只保留 ss_session_id。
- training_sessions.session_type 列：TrainingSession 模型改用 mode 字段；session_type 仅 StudySpaceSession 在用（另一张表）。

均经 grep 确认 app/ 内无引用、无数据依赖。downgrade 对称重建以保迁移链可逆。

Revision ID: 048
Revises: 047
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # training_sessions 两个废弃列（drop_column 连带移除其 FK 约束）
    op.drop_column("training_sessions", "studyspace_session_id")
    op.drop_column("training_sessions", "session_type")
    # 孤儿表 uploaded_files（先索引后表）
    op.drop_index("ix_uploaded_files_user_id", table_name="uploaded_files")
    op.drop_table("uploaded_files")


def downgrade() -> None:
    # 对称重建（镜像迁移 016 的原始定义）
    op.create_table(
        "uploaded_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False, server_default="image"),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_uploaded_files_user_id", "uploaded_files", ["user_id"])
    op.add_column("training_sessions", sa.Column(
        "session_type", sa.String(20), nullable=False, server_default="kp_practice",
    ))
    op.add_column("training_sessions", sa.Column(
        "studyspace_session_id", UUID(as_uuid=True),
        sa.ForeignKey("studyspace_sessions.id", ondelete="SET NULL"), nullable=True,
    ))
