import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class PrerequisiteEdge(Base):
    """先修依赖边（学习内核 P1）：from_kp 是 to_kp 的先修——学 to 之前应先掌握 from。

    整体近似偏序（KST，M8）；建边时防自环 + 防成环（见 graph_service）。
    """
    __tablename__ = "prerequisite_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    from_kp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    to_kp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="llm")  # 'llm'|'manual'|'inferred'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (UniqueConstraint("from_kp_id", "to_kp_id", name="uq_prereq_edge"),)
