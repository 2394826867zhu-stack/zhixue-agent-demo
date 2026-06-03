"""项目树状路径服务 — v2 PRD 行 388-426

- 树状结构 + 路径高亮（行 389）
- 节点颜色按知识卡难度蓝/紫/金（行 394）
- 节点重要性通过大小/边框/边缘光表达（行 395）
- 节点点击 → 玻璃气泡（行 399）
- 完成度 vs 掌握度 分离（行 408-410）
- 节点不允许用户手动新增/删除，由 Agent 自动添加（9.1 行 621）
"""
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.project import Project, ProjectTreeNode
from app.models.knowledge_point import KnowledgePoint
from app.models.curriculum import CurriculumChapter
from app.schemas.project import TreeNodeOut, TreeNodeBubble
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


class ProjectTreeService:

    async def get_tree(
        self, db: AsyncSession, project_id: str, user_id: str,
    ) -> list[TreeNodeOut]:
        """返回项目所有树节点的扁平列表 + parent_id 关系，由前端组装树。"""
        await self._assert_project_access(db, project_id, user_id)
        result = await db.execute(
            select(ProjectTreeNode)
            .where(ProjectTreeNode.project_id == uuid.UUID(project_id))
            .order_by(ProjectTreeNode.depth.asc(), ProjectTreeNode.sort_order.asc())
        )
        nodes = list(result.scalars().all())
        return [TreeNodeOut.model_validate(n) for n in nodes]

    async def get_node_bubble(
        self, db: AsyncSession, project_id: str, node_id: str, user_id: str,
    ) -> TreeNodeBubble:
        """节点点击气泡详情（PRD 行 402-410）。"""
        await self._assert_project_access(db, project_id, user_id)
        result = await db.execute(
            select(ProjectTreeNode).where(
                ProjectTreeNode.id == uuid.UUID(node_id),
                ProjectTreeNode.project_id == uuid.UUID(project_id),
            )
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise NotFoundError("节点不存在")

        # 课程描述：真填充——优先关联 KP 的 content（其次 name），再次关联章节 lesson_title，
        # 皆无则空串。此前硬编码 "" 占位，使契约 course_description 恒为空（审计 L1 幻觉）。
        course_description = ""
        if node.kp_id is not None:
            kp = (await db.execute(
                select(KnowledgePoint.content, KnowledgePoint.name)
                .where(KnowledgePoint.id == node.kp_id)
            )).first()
            if kp is not None:
                course_description = kp.content or kp.name or ""
        elif node.curriculum_chapter_id is not None:
            lesson = (await db.execute(
                select(CurriculumChapter.lesson_title)
                .where(CurriculumChapter.id == node.curriculum_chapter_id)
            )).scalar_one_or_none()
            course_description = lesson or ""

        return TreeNodeBubble(
            node=TreeNodeOut.model_validate(node),
            course_title=node.title,
            course_description=course_description,
            can_start_study=node.status in ("available", "in_progress"),
            can_start_quiz=node.completion_pct >= 1.0 or node.status == "completed",
        )

    async def mark_completed(
        self, db: AsyncSession, project_id: str, node_id: str, user_id: str,
    ) -> ProjectTreeNode:
        """学习完 + 测验通过 后由 studyspace_service / training_service 调用。

        v0.27 Q-03 · 完成时自动解锁直接子节点（parent → children locked→available）。
        """
        await self._assert_project_access(db, project_id, user_id)
        nid = uuid.UUID(node_id)
        await db.execute(
            update(ProjectTreeNode)
            .where(
                ProjectTreeNode.id == nid,
                ProjectTreeNode.project_id == uuid.UUID(project_id),
            )
            .values(
                status="completed",
                completion_pct=1.0,
                completed_at=datetime.now(timezone.utc),
            )
        )
        # 解锁子节点（PRD 行 394 推荐学习顺序）
        await db.execute(
            update(ProjectTreeNode)
            .where(
                ProjectTreeNode.parent_id == nid,
                ProjectTreeNode.status == "locked",
            )
            .values(status="available")
        )
        await db.commit()
        result = await db.execute(
            select(ProjectTreeNode).where(ProjectTreeNode.id == nid)
        )
        node = result.scalar_one()

        # v0.29 Memory · phase 完成 → 写 episode（Q5 锁定）
        # phase = depth 1 节点（树的二级），完成时记录里程碑
        try:
            if node.depth == 1:  # phase level
                from app.services.episodic_memory_service import record_event
                await record_event(
                    db, user_id=uuid.UUID(user_id),
                    event_kind="phase_completed",
                    summary=f"完成项目阶段「{node.title}」。",
                    detail={"node_id": str(nid), "title": node.title, "tier": node.difficulty},
                    ref_project_id=uuid.UUID(project_id),
                    emotional_tone="positive",
                )
        except Exception as _e:
            import logging
            logging.getLogger(__name__).warning(f"phase_completed episode hook failed: {_e}")
        return node

    async def update_mastery(
        self, db: AsyncSession, node_id: str, mastery_pct: float,
    ) -> None:
        """测验后由 training_service 调用更新掌握度。"""
        if not 0.0 <= mastery_pct <= 1.0:
            raise ValidationError("mastery_pct 必须在 0-1 之间")
        await db.execute(
            update(ProjectTreeNode)
            .where(ProjectTreeNode.id == uuid.UUID(node_id))
            .values(mastery_pct=mastery_pct)
        )
        await db.commit()

    async def update_progress(
        self, db: AsyncSession, node_id: str, completion_pct: float,
    ) -> None:
        """学习推进时由 studyspace_service 调用。

        v0.27 Q-03 · completion 满 1.0 时自动解锁子节点。
        """
        if not 0.0 <= completion_pct <= 1.0:
            raise ValidationError("completion_pct 必须在 0-1 之间")
        nid = uuid.UUID(node_id)
        values: dict = {
            "completion_pct": completion_pct,
            "last_studied_at": datetime.now(timezone.utc),
        }
        if completion_pct >= 1.0:
            values["status"] = "completed"
            values["completed_at"] = datetime.now(timezone.utc)
        elif completion_pct > 0:
            values["status"] = "in_progress"
        await db.execute(
            update(ProjectTreeNode)
            .where(ProjectTreeNode.id == nid)
            .values(**values)
        )
        # 解锁子节点（仅当本节点完成时）
        if completion_pct >= 1.0:
            await db.execute(
                update(ProjectTreeNode)
                .where(
                    ProjectTreeNode.parent_id == nid,
                    ProjectTreeNode.status == "locked",
                )
                .values(status="available")
            )
        await db.commit()

    # ── Agent 工具调用：添加节点 ────────────────────────────────────
    # 不暴露为用户 API（PRD 9.1 行 621：节点不允许用户手动新增）
    async def add_node_internal(
        self,
        db: AsyncSession,
        project_id: str,
        title: str,
        difficulty: str = "blue",
        parent_id: str | None = None,
        kp_id: str | None = None,
        phase_id: str | None = None,
        importance: int = 1,
        is_on_main_path: bool = False,
    ) -> ProjectTreeNode:
        pid = uuid.UUID(project_id)
        parent = None
        depth = 0
        if parent_id:
            parent_result = await db.execute(
                select(ProjectTreeNode).where(ProjectTreeNode.id == uuid.UUID(parent_id))
            )
            parent = parent_result.scalar_one_or_none()
            if parent is None:
                raise NotFoundError("父节点不存在")
            depth = parent.depth + 1

        node = ProjectTreeNode(
            project_id=pid,
            parent_id=uuid.UUID(parent_id) if parent_id else None,
            depth=depth,
            phase_id=uuid.UUID(phase_id) if phase_id else None,
            kp_id=uuid.UUID(kp_id) if kp_id else None,
            title=title,
            difficulty=difficulty,
            status="locked" if depth > 0 else "available",
            importance=importance,
            is_on_main_path=is_on_main_path,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    # ── 内部 ───────────────────────────────────────────────────────────

    async def _assert_project_access(
        self, db: AsyncSession, project_id: str, user_id: str,
    ) -> None:
        result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        proj = result.scalar_one_or_none()
        if proj is None:
            raise NotFoundError("项目不存在")
        if str(proj.user_id) != user_id:
            raise PermissionDeniedError("无权访问此项目")


project_tree_service = ProjectTreeService()
