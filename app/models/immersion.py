"""沉浸模式 — v2 PRD 6.1 / 9.9

- 场景：书桌 / 房间（第一版）
- BGM / 白噪音入口（9.9 行 686）
- 番茄钟循环自动进入下一轮（9.9 行 687）
- Agent 状态机：idle / thinking / speaking / focus / celebrate / reward（9.10 行 696）

迁移：alembic 021_v2_immersion_agent.py
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PgEnum
from app.core.database import Base


SCENE_KIND = PgEnum(
    "desk_room",     # 书桌 / 房间（默认）
    "library",       # 图书馆（v3）
    "cafe",          # 咖啡馆（v3）
    "tech_space",    # 科技空间（v3）
    name="immersion_scene_kind", create_type=True,
)

IMMERSION_STATUS = PgEnum(
    "active", "paused", "completed", "abandoned",
    name="immersion_status", create_type=True,
)

AGENT_STATE_KIND = PgEnum(
    # PRD 9.10 行 696：demo 第一版全部做 6 个
    "idle", "thinking", "speaking", "focus", "celebrate", "reward",
    # PRD 行 168：完整库后续扩展
    "remind", "sleepy", "confused", "error",
    name="agent_state_kind", create_type=True,
)


class ImmersionScene(Base):
    """沉浸场景资产 — 系统级目录（PRD 行 579：可与商店/装扮联动）。"""
    __tablename__ = "immersion_scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(SCENE_KIND, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 资源 URLs（前端读取展示）
    background_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bgm_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    white_noise_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 装扮/付费

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )


class ImmersionSession(Base):
    """沉浸模式会话 — 一次进入沉浸+番茄钟+退出的完整记录。

    PRD 6.1 行 376：学习时长只入全局，不绑项目。
    """
    __tablename__ = "immersion_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("immersion_scenes.id", ondelete="RESTRICT"), nullable=False,
    )

    status: Mapped[str] = mapped_column(IMMERSION_STATUS, nullable=False, server_default="active")

    # 番茄钟配置（PRD 6.1 行 372 自定义）
    focus_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="25")
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    long_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")

    # 累计指标
    pomodoros_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_focus_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # 音频开关
    bgm_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    white_noise_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentAvatarState(Base):
    """单个用户的 Agent 当前 avatar 状态机快照。

    PRD 2.1 行 167-170：状态库 idle/thinking/speaking/focus/celebrate/reward 等。
    PRD 9.10 行 696：demo 第一版 6 个 + 后续 4 个。

    每个用户单行（user_id 唯一）。Agent 状态随交互更新，前端读取以渲染对应动画/表情。
    """
    __tablename__ = "agent_avatar_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    current_state: Mapped[str] = mapped_column(AGENT_STATE_KIND, nullable=False, server_default="idle")
    state_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")
    # 例：{"thinking_about": "笔记生成"}、{"celebrating": "连击 7 天"}

    last_transition_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
