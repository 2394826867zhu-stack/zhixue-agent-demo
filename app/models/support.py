"""E-05 · 自建 In-app 客服：会话(thread) + 消息(message)。

刻意不引第三方（Intercom 等）：复用现有鉴权/通知基建，数据自有可控。
- SupportThread：一个用户的一条客服会话，带状态机 open→pending→resolved→closed。
- SupportMessage：会话内的一条消息，sender 区分 user / staff / system。
用户发起会话或追加消息后，系统会自动回执一条 system 消息，保证不出现「发了没人理」的死寂。
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


# 会话状态：open=待客服处理 / pending=已回复待用户 / resolved=已解决 / closed=已关闭
THREAD_STATUSES = ("open", "pending", "resolved", "closed")
# 消息发送方：user=用户 / staff=人工客服 / system=系统自动回执
MESSAGE_SENDERS = ("user", "staff", "system")


class SupportThread(Base):
    __tablename__ = "support_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)

    # 最近一条消息时间，用于会话列表排序
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    # 用户最后读到的时间，用于算未读
    user_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )

    sender: Mapped[str] = mapped_column(String(20), nullable=False)  # user | staff | system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


# 会话列表常用复合排序索引
Index("ix_support_threads_user_last_msg", SupportThread.user_id, SupportThread.last_message_at.desc())
