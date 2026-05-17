import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.core.database import Base


class PathStage(Base):
    __tablename__ = "path_stages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    nodes: Mapped[list["PathNode"]] = relationship(
        "PathNode", back_populates="stage",
        cascade="all, delete-orphan",
        order_by="PathNode.sort_order",
    )

    @property
    def progress(self) -> float:
        if not self.nodes:
            return 0.0
        done = sum(1 for n in self.nodes if n.status == "done")
        return round(done / len(self.nodes), 2)


class PathNode(Base):
    __tablename__ = "path_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("path_stages.id", ondelete="CASCADE"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "lesson" | "review" | "training" | "project"

    status: Mapped[str] = mapped_column(String(20), default="locked", nullable=False)
    # "locked" | "current" | "done" | "review"

    subject: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    reward: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FK to a note this node is about (optional)
    note_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)

    # Related KP UUIDs stored as PostgreSQL UUID array
    kp_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False, server_default="{}")

    # Prerequisite node IDs stored as UUID array
    prerequisite_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False, server_default="{}")

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    stage: Mapped["PathStage"] = relationship("PathStage", back_populates="nodes")
