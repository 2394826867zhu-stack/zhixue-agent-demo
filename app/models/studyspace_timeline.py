"""StudySpace 垂直时间线节点 — v2 PRD 行 436-448

PRD 决策：
- 行 436：阶段切换视觉选 C 垂直时间线
- 行 437：学习过程像真实学习记录流，从上到下自然展开
- 行 438：必须沉淀 7 类内容
    1. 学习内容（content）
    2. 知识点（kp_extracted）
    3. 闪卡结果（flashcard_result）
    4. 训练结果（training_result）
    5. 错题（mistake）
    6. 复盘（reflection）
    7. Agent 对话痕迹（agent_message）
- 行 444-448 编辑权限：
    - 笔记 / 知识点 / 复盘 → 用户可编辑 (is_editable=True)
    - 训练结果 / 错题 / 判题事实 → 不可改写 (is_editable=False)
    - Agent 关键操作 → 不随意改写，可通过追加修正节点更新

迁移：alembic 022_v2_ss_timeline.py
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PgEnum
from app.core.database import Base


TIMELINE_NODE_KIND = PgEnum(
    "content",            # 学习内容（讲义片段、用户笔记摘录）
    "kp_extracted",       # 提炼出的知识点
    "flashcard_result",   # 闪卡复习结果
    "training_result",    # 训练答题结果
    "mistake",            # 错题归入
    "reflection",         # 用户复盘 / 总结
    "agent_message",      # Agent 关键发言 / 调度结果
    "agent_action",       # Agent 调度（生成笔记 / 出题 / 复盘等）
    name="ss_timeline_node_kind",
    create_type=True,
)


class StudySpaceTimelineNode(Base):
    """StudySpace 会话内的一条时间线节点。"""
    __tablename__ = "studyspace_timeline_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studyspace_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    kind: Mapped[str] = mapped_column(TIMELINE_NODE_KIND, nullable=False)

    # 节点正文 + 任意结构化扩展
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")
    # 例：flashcard_result → {"flashcard_id":..., "rating":3, "duration_ms":4500}
    #     training_result  → {"question_id":..., "score":85, "is_wrong":false}
    #     kp_extracted     → {"kp_id":..., "name":"...", "bloom_level":"apply"}
    #     agent_action     → {"tool":"generate_note", "args":{...}, "result_ref":...}

    # 可选关联（便于跳转/反查）
    ref_kp_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True,
    )
    ref_flashcard_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flashcards.id", ondelete="SET NULL"), nullable=True,
    )
    ref_training_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_questions.id", ondelete="SET NULL"), nullable=True,
    )
    ref_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notes.id", ondelete="SET NULL"), nullable=True,
    )

    # 时间线顺序（按 created_at 已足够，但显式 sort_order 留给"追加修正"插入）
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 编辑权限（PRD 行 444-448）
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # 训练 / 错题 / Agent 关键操作判定后端写时设为 false

    # 追加修正：若是修正旧节点，指向被修正节点
    amends_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("studyspace_timeline_nodes.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
