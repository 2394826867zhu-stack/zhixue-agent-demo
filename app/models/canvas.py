"""StudySpace 画板 / 手写区笔画 — v2 PRD 9.3 行 636

存储为 SVG path 的 d 属性串 + 颜色 / 笔刷宽度。
前端实时绘制时本地持有；用户保存或离开时批量提交。

迁移：alembic 023
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class CanvasStroke(Base):
    """StudySpace 画板上的一条笔画。"""
    __tablename__ = "ss_canvas_strokes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studyspace_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )

    # SVG path d 属性（M ... L ... Q ... 等命令串）
    path_d: Mapped[str] = mapped_column(Text, nullable=False)

    # 笔刷
    color: Mapped[str] = mapped_column(String(20), nullable=False, server_default="#1F2937")
    stroke_width: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.0")
    opacity: Mapped[float] = mapped_column(Float, nullable=False, server_default="1.0")

    # 笔画在哪一页（同一个 SS 会话可能有多页画板）
    page_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # 笔画顺序（撤销/重做用）
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # 可选：扩展元数据（如笔型 pen/highlighter/eraser、压感等）
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
