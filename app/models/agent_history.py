"""Agent 控制台浏览记录 + 对话搜索 — v2 PRD 9.7 行 669-673

- 行 669：AI 深度控制台第一版需要浏览记录入口
- 行 673：控制台对话记录支持搜索

历史对话已经存在 Redis（agent_service.load_history / save_history），24h TTL，
最多 20 条。本表用于「持久化 / 跨会话浏览 + 搜索」的补充：
  - 用户在控制台点击"对话浏览记录"时显示最近 N 个会话
  - 用户输入关键词搜索时全文检索消息内容（pg trigram 不强求，简单 ILIKE 起步）

迁移：alembic 023
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class AgentConversationLog(Base):
    """Agent 会话的轻量摘要 + 全文索引来源。

    一个 session_id 对应多条消息，但本表只存"会话头"和首末消息预览，
    便于浏览列表展示。详细消息仍走 Redis（短期）。
    """
    __tablename__ = "agent_conversation_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # 与 agent_service Redis 中的 session_id 对齐

    # 浏览列表展示
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 自动取首条 user 消息前 50 字

    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 最后一条消息预览（前 200 字）

    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 搜索原文（首末消息 + 关键工具结果，concat 用于 ILIKE）
    search_blob: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 工具调用记录（哪些工具被这个会话调用过）
    tools_called: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")
    # 例：{"create_project_from_dialog": 1, "diagnose_learning": 2}

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True,
    )
