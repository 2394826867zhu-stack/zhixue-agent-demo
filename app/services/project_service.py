"""项目服务 — v2 PRD 学习工作台核心

PRD 章节:
- 3.4 我的项目（行 311-339）
- 项目页时间线 + 树状路径（行 379-426）
- 9.1 项目编辑只允许名+简介（行 615）
- 9.2 Agent 对话式收集 + 预览卡确认（行 624-628）
"""
import json
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from app.models.project import (
    Project, ProjectPhase, ProjectMilestone, ProjectTreeNode,
)
from app.models.flashcard import Flashcard
from app.models.note import Note
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectReorderRequest,
    ProjectInitDraft, ProjectPreviewCard, ProjectConfirmRequest,
    ProjectDataSummary,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.llm.client import LLMClient
from app.llm.prompts.project_init import SYSTEM_PROJECT_DRAFT, PROJECT_DRAFT_FROM_DIALOG
from app.llm.prompts.project_tree import SYSTEM_PROJECT_TREE, PROJECT_TREE_GENERATE

logger = logging.getLogger(__name__)


class ProjectService:

    # ── 列表 / 详情 ─────────────────────────────────────────────────────

    async def list_projects(
        self,
        db: AsyncSession,
        user_id: str,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Project], int]:
        uid = uuid.UUID(user_id)
        base = select(Project).where(Project.user_id == uid)
        if status:
            base = base.where(Project.status == status)
        else:
            # 默认不展示 archived
            base = base.where(Project.status != "archived")
        total = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        q = (
            base.options(
                selectinload(Project.phases),
                selectinload(Project.milestones),
            )
            .order_by(Project.sort_order.asc(), Project.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await db.execute(q)
        return list(result.scalars().all()), total

    async def get_project(self, db: AsyncSession, project_id: str, user_id: str) -> Project:
        proj = await self._fetch_project(db, project_id, user_id)
        # eager-load 关系
        await db.refresh(proj, ["phases", "milestones"])
        return proj

    # ── 创建 ────────────────────────────────────────────────────────────

    async def create_project(
        self, db: AsyncSession, user_id: str, data: ProjectCreate,
    ) -> Project:
        """直接结构化创建（用于官方课程派生 / Agent 已收集完整字段的场景）。"""
        uid = uuid.UUID(user_id)

        # 计算 sort_order = 当前最大值 + 1
        max_sort = await db.execute(
            select(func.coalesce(func.max(Project.sort_order), -1)).where(Project.user_id == uid)
        )
        next_sort = (max_sort.scalar() or -1) + 1

        proj = Project(
            user_id=uid,
            name=data.name,
            summary=data.summary,
            source=data.source,
            subject=data.subject,
            curriculum_chapter_id=data.curriculum_chapter_id,
            target_completion_date=data.target_completion_date,
            weekly_hours=data.weekly_hours,
            sort_order=next_sort,
            started_at=datetime.now(timezone.utc),
        )
        db.add(proj)
        await db.commit()
        # 必须显式 load 关系：端点用 ProjectListItem.model_validate(proj) 会同步
        # 访问 proj.phases，未 load 会在异步上下文触发 MissingGreenlet。
        await db.refresh(proj, attribute_names=["phases", "milestones"])
        return proj

    async def create_from_draft(
        self, db: AsyncSession, user_id: str, draft: ProjectInitDraft,
    ) -> ProjectPreviewCard:
        """根据 Agent 整理的 draft 计算 preview card（不入库）。

        PRD 行 333：用户点击确认之前必须看到 Agent 理解的项目骨架。
        """
        # 默认四阶段
        phases = [
            {"name": "基础", "description": "建立知识地图与核心概念", "est_weeks": 2},
            {"name": "强化", "description": "深度训练与错题修正", "est_weeks": 2},
            {"name": "复习", "description": "FSRS 复盘与查漏补缺", "est_weeks": 1},
            {"name": "冲刺", "description": "限时模拟与最终调整", "est_weeks": 1},
        ]
        # 关键事件初版只埋入目标完成日期
        milestones = []
        if draft.target_completion_date:
            milestones.append({
                "title": "项目截止",
                "type": "deadline",
                "days_from_now": (draft.target_completion_date - datetime.now(timezone.utc)).days,
            })
        return ProjectPreviewCard(
            draft=draft,
            proposed_phases=phases,
            proposed_milestones=milestones,
            proposed_tree_summary={
                "total_nodes": 0,  # Agent 后续填充
                "blue_count": 0,
                "purple_count": 0,
                "gold_count": 0,
            },
            estimated_total_hours=(draft.weekly_hours or 5) * 6,
        )

    async def confirm_preview(
        self, db: AsyncSession, user_id: str, req: ProjectConfirmRequest,
    ) -> Project:
        """用户确认 preview 后正式生成项目 + phases + milestones。

        PRD 行 339：Agent 根据信息进行全面项目初始化，生成结构/周期/时间线/树/初始知识模型/推荐顺序/测验规划。
        Tree 节点由 Agent 后续调用 project_tree_service 添加（PRD 9.1 行 621 节点不允许用户手动新增）。
        """
        uid = uuid.UUID(user_id)
        draft = req.preview.draft

        max_sort = await db.execute(
            select(func.coalesce(func.max(Project.sort_order), -1)).where(Project.user_id == uid)
        )
        next_sort = (max_sort.scalar() or -1) + 1

        proj = Project(
            user_id=uid,
            name=draft.name,
            summary=draft.summary,
            source="user_project",
            subject=draft.subject,
            target_completion_date=draft.target_completion_date,
            weekly_hours=draft.weekly_hours,
            init_context=draft.init_context,
            sort_order=next_sort,
            started_at=datetime.now(timezone.utc),
        )
        db.add(proj)
        await db.flush()  # 拿到 proj.id

        # phases
        now = datetime.now(timezone.utc)
        cursor = now
        for idx, p in enumerate(req.preview.proposed_phases):
            weeks = int(p.get("est_weeks", 2))
            end = cursor + timedelta(weeks=weeks)
            db.add(ProjectPhase(
                project_id=proj.id,
                name=p["name"],
                description=p.get("description", ""),
                start_date=cursor,
                end_date=end,
                sort_order=idx,
                is_current=(idx == 0),
            ))
            cursor = end

        # milestones
        for m in req.preview.proposed_milestones:
            event = now + timedelta(days=int(m.get("days_from_now", 30)))
            db.add(ProjectMilestone(
                project_id=proj.id,
                title=m["title"],
                description=m.get("description", ""),
                milestone_type=m.get("type", "custom"),
                event_date=event,
            ))

        await db.commit()
        await db.refresh(proj)
        return proj

    # ── 更新 / 删除 ─────────────────────────────────────────────────────

    async def update_project(
        self, db: AsyncSession, project_id: str, user_id: str, data: ProjectUpdate,
    ) -> Project:
        """PRD 9.1 行 615：第一版只允许修改名+简介。"""
        proj = await self._fetch_project(db, project_id, user_id)
        if data.name is not None:
            proj.name = data.name
        if data.summary is not None:
            proj.summary = data.summary
        await db.commit()
        await db.refresh(proj)
        return proj

    async def delete_project(self, db: AsyncSession, project_id: str, user_id: str) -> None:
        """PRD 行 323：系统确认弹窗，第一版不做回收站。"""
        proj = await self._fetch_project(db, project_id, user_id)
        await db.delete(proj)
        await db.commit()

    async def reorder(
        self, db: AsyncSession, user_id: str, req: ProjectReorderRequest,
    ) -> None:
        """PRD 行 319：用户拖动排序。"""
        uid = uuid.UUID(user_id)
        for item in req.items:
            await db.execute(
                update(Project)
                .where(Project.id == item.project_id, Project.user_id == uid)
                .values(sort_order=item.sort_order)
            )
        await db.commit()

    # ── LLM 驱动 · 从对话生成 draft ─────────────────────────────────────

    async def draft_from_dialog(
        self, db: AsyncSession, user_id: str, dialog: str,
    ) -> ProjectPreviewCard:
        """Agent 把用户的自然语言对话整理为项目骨架（PRD 9.2 行 624）。

        失败时回退到 create_from_draft 的硬编码 4 阶段模板。
        """
        llm = LLMClient()
        prompt = PROJECT_DRAFT_FROM_DIALOG.format(dialog=dialog[:2000])
        try:
            raw = await llm.generate(
                prompt=prompt,
                system=SYSTEM_PROJECT_DRAFT,
                user_id=user_id,
                endpoint="project.draft_from_dialog",
            )
            data = _extract_json(raw)
            draft = ProjectInitDraft(**data["draft"])
            return ProjectPreviewCard(
                draft=draft,
                proposed_phases=data.get("proposed_phases", []),
                proposed_milestones=data.get("proposed_milestones", []),
                proposed_tree_summary={
                    "total_nodes": 0, "blue_count": 0, "purple_count": 0, "gold_count": 0,
                },
                estimated_total_hours=(draft.weekly_hours or 5) * sum(
                    int(p.get("est_weeks", 1)) for p in data.get("proposed_phases", [])
                ),
            )
        except Exception as e:
            logger.warning("draft_from_dialog LLM failed, fallback to template: %s", e)
            # 回退：用户输入第一行当 name，其余当 summary
            lines = [ln.strip() for ln in dialog.split("\n") if ln.strip()]
            fallback_draft = ProjectInitDraft(
                name=(lines[0] if lines else "新项目")[:20],
                summary="\n".join(lines[1:])[:200],
                init_context={"user_raw": dialog[:500]},
            )
            return await self.create_from_draft(db, user_id, fallback_draft)

    # ── LLM 驱动 · 生成树节点 ───────────────────────────────────────────

    async def generate_tree_nodes(
        self, db: AsyncSession, project_id: str, user_id: str,
    ) -> int:
        """项目确认创建后，由 Agent 调用此方法填充树节点。

        PRD 9.1 行 621：节点不允许用户手动新增 / 删除，由 Agent 自动添加。
        返回插入的节点数。
        """
        proj = await self._fetch_project(db, project_id, user_id)

        # 已有节点 → 跳过（避免重复生成）
        exists = await db.execute(
            select(func.count(ProjectTreeNode.id))
            .where(ProjectTreeNode.project_id == proj.id)
        )
        if (exists.scalar() or 0) > 0:
            return 0

        # 取 phases
        phases_q = await db.execute(
            select(ProjectPhase)
            .where(ProjectPhase.project_id == proj.id)
            .order_by(ProjectPhase.sort_order.asc())
        )
        phases = list(phases_q.scalars().all())
        phase_lookup = {p.name: p for p in phases}
        total_weeks = sum(
            (p.end_date - p.start_date).days // 7
            for p in phases if p.start_date and p.end_date
        ) or 6

        llm = LLMClient()
        prompt = PROJECT_TREE_GENERATE.format(
            name=proj.name,
            summary=proj.summary or "",
            subject=proj.subject or "通用",
            phases=", ".join(p.name for p in phases),
            total_weeks=total_weeks,
            known_kps="（无）",
        )
        try:
            raw = await llm.generate(
                prompt=prompt,
                system=SYSTEM_PROJECT_TREE,
                user_id=user_id,
                endpoint="project.generate_tree",
            )
            data = _extract_json(raw)
        except Exception as e:
            logger.warning("generate_tree LLM failed, project=%s: %s", project_id, e)
            return 0

        # 根节点
        root_meta = data.get("root", {})
        root = ProjectTreeNode(
            project_id=proj.id,
            parent_id=None,
            depth=0,
            phase_id=phases[0].id if phases else None,
            title=root_meta.get("title", proj.name)[:120],
            difficulty=root_meta.get("difficulty", "blue"),
            importance=int(root_meta.get("importance", 3)),
            is_on_main_path=bool(root_meta.get("is_on_main_path", True)),
            status="available",
            sort_order=0,
        )
        db.add(root)
        await db.flush()

        # 子节点（两轮，第一轮挂在 root / 第二轮挂在第一轮的标题上）
        title_to_node: dict[str, ProjectTreeNode] = {root.title: root}
        nodes_meta = data.get("nodes", [])
        # 按 depth 升序，确保 parent 先创建
        nodes_meta.sort(key=lambda n: int(n.get("depth", 1)))

        for idx, nmeta in enumerate(nodes_meta):
            parent_title = nmeta.get("parent_title", root.title)
            parent = title_to_node.get(parent_title, root)
            phase_name = nmeta.get("phase_name")
            phase = phase_lookup.get(phase_name) if phase_name else None
            node = ProjectTreeNode(
                project_id=proj.id,
                parent_id=parent.id,
                depth=int(nmeta.get("depth", parent.depth + 1)),
                phase_id=phase.id if phase else (phases[0].id if phases else None),
                title=str(nmeta.get("title", f"节点 {idx+1}"))[:120],
                difficulty=nmeta.get("difficulty", "blue"),
                importance=int(nmeta.get("importance", 1)),
                is_on_main_path=bool(nmeta.get("is_on_main_path", False)),
                status="locked",
                sort_order=idx,
            )
            db.add(node)
            title_to_node[node.title] = node

        await db.commit()
        return len(nodes_meta) + 1

    # ── 数据栏 ──────────────────────────────────────────────────────────

    async def get_data_summary(
        self, db: AsyncSession, project_id: str, user_id: str,
    ) -> ProjectDataSummary:
        """项目页底部数据栏环状图（PRD 行 410）。"""
        proj = await self._fetch_project(db, project_id, user_id)

        nodes_q = await db.execute(
            select(
                func.count(ProjectTreeNode.id),
                func.count(ProjectTreeNode.id).filter(ProjectTreeNode.status == "completed"),
            ).where(ProjectTreeNode.project_id == proj.id)
        )
        nodes_total, nodes_done = nodes_q.one()

        # 暂用粗略统计；后续 mistake/flashcard 模型加 project_id 后精细化
        return ProjectDataSummary(
            completion_pct=proj.completion_pct,
            mastery_pct=proj.mastery_pct,
            tree_nodes_total=nodes_total or 0,
            tree_nodes_completed=nodes_done or 0,
            flashcards_total=0,
            flashcards_due=0,
            mistakes_total=0,
            notes_total=0,
            study_minutes=0,
        )

    # ── 内部 ───────────────────────────────────────────────────────────

    async def _fetch_project(
        self, db: AsyncSession, project_id: str, user_id: str,
    ) -> Project:
        try:
            pid = uuid.UUID(project_id)
            uid = uuid.UUID(user_id)
        except (ValueError, TypeError):
            raise ValidationError("project_id 或 user_id 格式不合法")

        result = await db.execute(select(Project).where(Project.id == pid))
        proj = result.scalar_one_or_none()
        if proj is None:
            raise NotFoundError("项目不存在")
        if proj.user_id != uid:
            raise PermissionDeniedError("无权访问此项目")
        return proj


_JSON_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


def _extract_json(raw: str) -> dict:
    """从 LLM 输出中提取 JSON（处理 ```json fences、或纯 JSON）。"""
    if "{" not in raw:
        raise ValueError("LLM 未返回 JSON")
    m = _JSON_RE.search(raw)
    if m:
        return json.loads(m.group(1).strip())
    # 否则尝试找第一个 { 和最后一个 } 之间
    start = raw.index("{")
    end = raw.rindex("}")
    return json.loads(raw[start:end + 1])


project_service = ProjectService()
