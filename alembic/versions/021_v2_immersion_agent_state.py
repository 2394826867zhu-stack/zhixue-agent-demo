"""v2 PRD · 沉浸场景 + Agent 状态机

PRD 6.1 / 9.9 / 9.10 / 2.1

Revision ID: 021
Revises: 020
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


scene_kind_enum = postgresql.ENUM(
    "desk_room", "library", "cafe", "tech_space",
    name="immersion_scene_kind", create_type=False,
)
immersion_status_enum = postgresql.ENUM(
    "active", "paused", "completed", "abandoned",
    name="immersion_status", create_type=False,
)
agent_state_kind_enum = postgresql.ENUM(
    "idle", "thinking", "speaking", "focus", "celebrate", "reward",
    "remind", "sleepy", "confused", "error",
    name="agent_state_kind", create_type=False,
)


def upgrade() -> None:
    # ── enums (raw SQL, idempotent) ─────────────────────────────────
    op.execute("CREATE TYPE immersion_scene_kind AS ENUM ('desk_room','library','cafe','tech_space')")
    op.execute("CREATE TYPE immersion_status AS ENUM ('active','paused','completed','abandoned')")
    op.execute(
        "CREATE TYPE agent_state_kind AS ENUM ("
        "'idle','thinking','speaking','focus','celebrate','reward',"
        "'remind','sleepy','confused','error')"
    )

    # ── immersion_scenes ────────────────────────────────────────────
    op.create_table(
        "immersion_scenes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", scene_kind_enum, nullable=False, unique=True),
        sa.Column("title", sa.String(60), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("background_url", sa.String(500), nullable=True),
        sa.Column("bgm_url", sa.String(500), nullable=True),
        sa.Column("white_noise_url", sa.String(500), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_premium", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── immersion_sessions ──────────────────────────────────────────
    op.create_table(
        "immersion_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", UUID(as_uuid=True), sa.ForeignKey("immersion_scenes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", immersion_status_enum, nullable=False, server_default="active"),
        sa.Column("focus_minutes", sa.Integer, nullable=False, server_default="25"),
        sa.Column("break_minutes", sa.Integer, nullable=False, server_default="5"),
        sa.Column("long_break_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("cycle_count", sa.Integer, nullable=False, server_default="4"),
        sa.Column("pomodoros_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_focus_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("bgm_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("white_noise_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_immersion_sessions_user_id", "immersion_sessions", ["user_id"])

    # ── agent_avatar_states ─────────────────────────────────────────
    op.create_table(
        "agent_avatar_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("current_state", agent_state_kind_enum, nullable=False, server_default="idle"),
        sa.Column("state_data", JSONB, nullable=False, server_default="{}"),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # ── 种子默认场景 ────────────────────────────────────────────────
    op.execute("""
        INSERT INTO immersion_scenes (id, kind, title, description, is_default, sort_order)
        VALUES (gen_random_uuid(), 'desk_room', '书桌 · 房间', '同桌自习场景，默认场景', true, 0)
    """)


def downgrade() -> None:
    op.drop_table("agent_avatar_states")
    op.drop_index("ix_immersion_sessions_user_id", "immersion_sessions")
    op.drop_table("immersion_sessions")
    op.drop_table("immersion_scenes")
    op.execute("DROP TYPE IF EXISTS agent_state_kind")
    op.execute("DROP TYPE IF EXISTS immersion_status")
    op.execute("DROP TYPE IF EXISTS immersion_scene_kind")
