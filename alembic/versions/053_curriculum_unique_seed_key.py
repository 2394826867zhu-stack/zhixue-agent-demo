"""curriculum_chapters 系统 seed 去重 + 部分唯一索引（防重部署/双 worker race 造重复）

根因：seed_curriculum 在 FastAPI lifespan 里每个 uvicorn worker 都跑，首启空库时
两 worker 同时「不存在→插入」→ 重复行；后续重启 `scalar_one_or_none()` 撞重复
→ MultipleResultsFound → 启动崩溃（任何重部署都会触发）。

修复：① 先去重存量（保留每唯一键 ctid 最小一行）② 对系统内容
（owner_user_id IS NULL）建部分唯一索引，从 DB 层杜绝重复 seed。
用户导入（owner_user_id 非空）不受约束。

Revision ID: 053
Revises: 052
Create Date: 2026-06-22
"""
from alembic import op


revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

_KEY = "subject, grade_type, grade_year, semester, chapter_index, lesson_index, textbook_version"


def upgrade() -> None:
    # ① 去重存量系统 seed（保留每唯一键 ctid 最小的一行）
    op.execute(
        f"""
        DELETE FROM curriculum_chapters a USING curriculum_chapters b
        WHERE a.ctid > b.ctid
          AND a.owner_user_id IS NULL AND b.owner_user_id IS NULL
          AND a.subject IS NOT DISTINCT FROM b.subject
          AND a.grade_type IS NOT DISTINCT FROM b.grade_type
          AND a.grade_year = b.grade_year
          AND a.semester = b.semester
          AND a.chapter_index = b.chapter_index
          AND a.lesson_index = b.lesson_index
          AND a.textbook_version IS NOT DISTINCT FROM b.textbook_version;
        """
    )
    # ② 部分唯一索引：仅约束系统内容（owner_user_id IS NULL）
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_curriculum_system_seed_key
        ON curriculum_chapters ({_KEY})
        WHERE owner_user_id IS NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_curriculum_system_seed_key;")
