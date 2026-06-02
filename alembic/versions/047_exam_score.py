"""G-P4-2 · 外部成绩锚：exams.score_pct（考后录入真实成绩百分比）。"""
from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exams", sa.Column("score_pct", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("exams", "score_pct")
