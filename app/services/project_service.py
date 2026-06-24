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
import hashlib
from sqlalchemy import select, func, update, delete, text
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
from app.services.framework_service import generate_framework

logger = logging.getLogger(__name__)

# ── 阶段模板按学科调性（INC-8 · 2026-06-24）─────────────────────────────────
# 不再对所有项目硬编码"基础/强化/复习"——按 subject 关键词选阶段骨架。
# 存量项目不受影响（阶段已入库）；仅新建项目走此模板。

_LANGUAGE_SUBJECTS = {
    "日语", "英语", "法语", "韩语", "德语", "西班牙语", "俄语", "意大利语",
    "葡萄牙语", "阿拉伯语", "泰语", "越南语", "印尼语", "马来语",
    "japanese", "english", "french", "korean", "german", "spanish",
}
_SCIENCE_SUBJECTS = {
    "数学", "物理", "化学", "生物", "信息", "信息技术",
    "math", "physics", "chemistry", "biology",
}
_HUMANITIES_SUBJECTS = {
    "历史", "语文", "政治", "地理", "社会", "道法",
    "history", "chinese", "politics", "geography",
}
_EXAM_KEYWORDS = {"备考", "EJU", "托福", "雅思", "高考", "中考", "考研", "TOEFL", "IELTS", "SAT",
                  "JLPT", "N1", "N2", "N3", "N4", "N5", "CEFR", "DELF", "DALF"}

# 阶段模板：(name, description, days)
_TONE_PHASES: dict[str, list[tuple[str, str, int]]] = {
    "language": [
        ("语音与文字", "建立发音与书写基础", 14),
        ("核心词汇与语法", "高频词汇与关键语法点", 28),
        ("场景应用", "日常对话与实用表达", 28),
        ("综合表达", "叙述、论述与文化理解", 14),
    ],
    "science": [
        ("概念与定理", "建立核心概念与定理基础", 21),
        ("证明与推导", "掌握推理方法与证明技巧", 28),
        ("应用与建模", "实际问题建模与综合应用", 21),
    ],
    "humanities": [
        ("主题与史实", "建立主题框架与关键史实", 21),
        ("证据与因果", "分析证据链与因果逻辑", 21),
        ("论证与批判", "多视角论证与批判性思维", 21),
    ],
    "exam": [
        ("能力诊断", "识别强弱项与靶向目标", 7),
        ("弱项靶向", "针对性强化薄弱环节", 28),
        ("真题模考", "限时模拟与实战训练", 21),
        ("冲刺", "高频考点速查与易错排查", 7),
    ],
    "default": [
        ("基础", "建立知识地图与核心概念", 14),
        ("强化", "深度训练与错题修正", 28),
        ("复习", "综合复盘与模拟冲刺", 18),
    ],
}


def _detect_tone(subject: str | None, source: str | None = None, summary: str | None = None) -> str:
    """根据学科+来源识别学习调性，返回阶段模板 key。"""
    s = (subject or "").strip()
    src = (source or "").strip()
    desc = (summary or "").strip()
    combined = f"{s} {desc}".lower()

    # 考试关键词优先（无论学科，提到备考就走 exam 模板）
    for kw in _EXAM_KEYWORDS:
        if kw.lower() in combined:
            return "exam"

    # 学科关键词匹配
    for lang_kw in _LANGUAGE_SUBJECTS:
        if lang_kw.lower() in s.lower():
            return "language"
    for sci_kw in _SCIENCE_SUBJECTS:
        if sci_kw.lower() in s.lower():
            return "science"
    for hum_kw in _HUMANITIES_SUBJECTS:
        if hum_kw.lower() in s.lower():
            return "humanities"

    # 无学科 → 默认（保持现有"基础/强化/复习"，向后兼容）
    return "default"


def _build_phases_for_tone(tone: str) -> list[tuple[str, str, int]]:
    """返回阶段模板列表。"""
    return _TONE_PHASES.get(tone, _TONE_PHASES["default"])


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
        await db.flush()

        # 按学科调性生成阶段（INC-8 · 2026-06-24）
        # 不再硬编码"基础/强化/复习"——语言/理科/文科/备考各有阶段骨架。
        now = datetime.now(timezone.utc)
        tone = _detect_tone(data.subject, data.source, data.summary)
        phase_templates = _build_phases_for_tone(tone)
        cursor = now
        for idx, (name, desc, days) in enumerate(phase_templates):
            end = cursor + timedelta(days=days)
            db.add(ProjectPhase(
                project_id=proj.id, name=name, description=desc,
                sort_order=idx, start_date=cursor, end_date=end,
                is_current=(idx == 0),
            ))
            cursor = end
        await db.commit()
        await db.refresh(proj, attribute_names=["phases", "milestones"])
        return proj

    async def create_from_draft(
        self, db: AsyncSession, user_id: str, draft: ProjectInitDraft,
    ) -> ProjectPreviewCard:
        """根据 Agent 整理的 draft 计算 preview card（不入库）。

        PRD 行 333：用户点击确认之前必须看到 Agent 理解的项目骨架。
        """
        # 按学科调性生成阶段预览（INC-8 · 2026-06-24）
        tone = _detect_tone(draft.subject, "user_project", draft.summary if hasattr(draft, 'summary') else None)
        phase_templates = _build_phases_for_tone(tone)
        phases = [
            {"name": name, "description": desc, "est_weeks": max(1, round(days / 7))}
            for name, desc, days in phase_templates
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
        # 端点用 ProjectListItem.model_validate(proj) 会同步访问 proj.phases，
        # 必须显式 load 关系，否则异步 lazy-load 触发 MissingGreenlet（审计 P1-1/P1-2）。
        await db.refresh(proj, attribute_names=["phases", "milestones"])
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
        # 端点用 ProjectListItem.model_validate(proj) 会同步访问 proj.phases，
        # 必须显式 load 关系，否则异步 lazy-load 触发 MissingGreenlet（审计 P1-1/P1-2）。
        await db.refresh(proj, attribute_names=["phases", "milestones"])
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

        # F6a 并发锁：同一项目同时只允许一个生成事务。前端轮询/重试会双发 generate，
        # 无锁时两个事务都见 count=0 → 都插入 → 重复节点（德语实测 ×4）。事务级 advisory
        # lock 在首次 commit(节点入库后) 自动释放；后到的事务等锁→拿锁→见 count>0→直接返回。
        # 镜像 task_service.generate_today 的做法。
        lock_key = int(hashlib.md5(f"tree:{proj.id}".encode()).hexdigest()[:8], 16) % (2**31)
        await db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

        # 已有节点 → 返回已有数量（幂等：不重复生成）
        exists = await db.execute(
            select(func.count(ProjectTreeNode.id))
            .where(ProjectTreeNode.project_id == proj.id)
        )
        existing_count = exists.scalar() or 0
        if existing_count > 0:
            return existing_count

        # 估算总周数（框架用；存量阶段提供粗略上限）
        phases_q = await db.execute(
            select(ProjectPhase)
            .where(ProjectPhase.project_id == proj.id)
            .order_by(ProjectPhase.sort_order.asc())
        )
        phases = list(phases_q.scalars().all())
        total_weeks = sum(
            (p.end_date - p.start_date).days // 7
            for p in phases if p.start_date and p.end_date
        ) or 8

        # F1b 纯生成式知识框架（弃模板/弃官方背书）：LLM 为这个项目量身生成
        # 阶段 + 大章节(depth1) > 小课时(depth2) + 每课 KP + 顺序先修边。
        framework = await generate_framework(
            name=proj.name, subject=proj.subject, summary=proj.summary,
            weeks=total_weeks, user_id=user_id,
        )
        if not framework:
            # 纯生成式失败 → 不退模板、不留半成品，置 failed 态（前端展示「生成失败·重试」，F2）
            proj.framework_status = "failed"
            await db.commit()
            logger.warning("framework generation failed for project=%s → framework_status=failed", project_id)
            return 0

        node_count = await self._build_tree_from_framework(db, proj, framework)
        proj.framework_status = "ready"
        await db.commit()
        return node_count

    async def _build_tree_from_framework(
        self, db: AsyncSession, proj: Project, framework: dict,
    ) -> int:
        """F1b：按纯生成式框架建 阶段 + 大章节(depth1)>小课时(depth2) + 每课 KP + 顺序先修边。

        模型语义：**大章节(depth1)=容器(无 KP，恒 available)；小课时(depth2)=可学单元(有 kp_id，
        locked/available/completed 生命周期)**。所有「可学/解锁/开始/任务」逻辑只认有 kp_id 的课时。
        用框架阶段重建 phases（作废 INC-8 模板；此时尚无 tree 节点引用旧 phase，删建安全）。
        """
        from app.models.knowledge_point import KnowledgePoint
        from app.models.prerequisite_edge import PrerequisiteEdge

        _DIFF = ["blue", "purple", "gold"]

        # 1. 用框架阶段替换旧阶段（纯生成式阶段，作废 INC-8 模板）
        await db.execute(delete(ProjectPhase).where(ProjectPhase.project_id == proj.id))
        cursor = datetime.now(timezone.utc)
        phase_lookup: dict[str, ProjectPhase] = {}
        fw_phases = [p for p in framework.get("phases", []) if isinstance(p, dict) and str(p.get("name", "")).strip()]
        for i, p in enumerate(fw_phases):
            wks = max(1, int(p.get("weeks", 4) or 4))
            ph = ProjectPhase(
                project_id=proj.id, name=str(p["name"])[:60],
                description=str(p.get("description", ""))[:500],
                start_date=cursor, end_date=cursor + timedelta(weeks=wks),
                sort_order=i, is_current=(i == 0),
            )
            db.add(ph)
            phase_lookup[ph.name] = ph
            cursor = cursor + timedelta(weeks=wks)
        await db.flush()
        default_phase = next(iter(phase_lookup.values()), None)

        def _diff_for(phase_name) -> str:
            ph = phase_lookup.get(phase_name or "")
            return _DIFF[min(ph.sort_order, 2)] if ph else "blue"

        # 2. 根节点
        root = ProjectTreeNode(
            project_id=proj.id, parent_id=None, depth=0,
            phase_id=(default_phase.id if default_phase else None),
            title=proj.name[:120], difficulty="blue", importance=3,
            is_on_main_path=True, status="available", sort_order=0,
        )
        db.add(root)
        await db.flush()

        # 3. 大章节(depth1) > 小课时(depth2) + 每课 KP
        node_count = 1
        sort = 1
        lesson_kp_ids: list[uuid.UUID] = []  # 按课时顺序 → 顺序先修边
        for ch in framework.get("chapters", []):
            if not isinstance(ch, dict) or not str(ch.get("title", "")).strip():
                continue
            ph = phase_lookup.get(ch.get("phase_name")) or default_phase
            diff = _diff_for(ch.get("phase_name"))
            chap = ProjectTreeNode(
                project_id=proj.id, parent_id=root.id, depth=1,
                phase_id=(ph.id if ph else None), title=str(ch["title"])[:120],
                difficulty=diff, importance=2, is_on_main_path=True,
                status="available", sort_order=sort,  # 章节是容器，恒 available
            )
            db.add(chap)
            await db.flush()
            node_count += 1
            sort += 1
            for ls in ch.get("lessons", []):
                if not isinstance(ls, dict) or not str(ls.get("title", "")).strip():
                    continue
                kp = KnowledgePoint(
                    user_id=proj.user_id, project_id=proj.id,
                    name=str(ls["title"])[:255], subject=proj.subject,
                    difficulty_tier=diff, mastery_status="new",
                    notebook_origin="user_project",
                )
                db.add(kp)
                await db.flush()
                lesson = ProjectTreeNode(
                    project_id=proj.id, parent_id=chap.id, depth=2,
                    phase_id=(ph.id if ph else None), kp_id=kp.id,
                    title=str(ls["title"])[:120], difficulty=diff, importance=1,
                    is_on_main_path=True, status="locked", sort_order=sort,
                )
                db.add(lesson)
                node_count += 1
                sort += 1
                lesson_kp_ids.append(kp.id)
        await db.flush()

        # 4. 解锁第一节课时（至少一节可学）
        if lesson_kp_ids:
            first_lesson = (await db.execute(
                select(ProjectTreeNode)
                .where(ProjectTreeNode.project_id == proj.id, ProjectTreeNode.depth == 2)
                .order_by(ProjectTreeNode.sort_order.asc()).limit(1)
            )).scalar_one_or_none()
            if first_lesson:
                first_lesson.status = "available"

        # 5. 顺序先修边（课时链）→ 给内核 frontier 依赖链（F4 据此驱动解锁）
        for a, b in zip(lesson_kp_ids, lesson_kp_ids[1:]):
            db.add(PrerequisiteEdge(user_id=proj.user_id, from_kp_id=a, to_kp_id=b, confidence=0.6, source="llm"))

        return node_count

    async def _anchor_nodes_to_kps(
        self, db: AsyncSession, proj: Project,
        title_to_node: dict[str, ProjectTreeNode],
    ) -> None:
        """INC-1 建树预生成 KP：每个 depth≥1 树节点锚定一个项目级 KP。

        直接建模型、不走 KP 服务——裸 KP 无内容,不入 RAG 索引(避免无意义向量)；
        内容随后续教学/笔记补齐后再由既有写入侧触发 RAG。幂等：已有 kp_id 的节点跳过。
        """
        from app.models.knowledge_point import KnowledgePoint
        pending: list[tuple[ProjectTreeNode, KnowledgePoint]] = []
        for node in title_to_node.values():
            if node.depth < 1 or node.kp_id:
                continue
            kp = KnowledgePoint(
                user_id=proj.user_id,
                project_id=proj.id,
                chapter_id=node.curriculum_chapter_id,
                name=str(node.title)[:255],
                subject=proj.subject,
                difficulty_tier=node.difficulty if node.difficulty in ("blue", "purple", "gold") else "blue",
                mastery_status="new",
                notebook_origin="user_project",
            )
            db.add(kp)
            pending.append((node, kp))
        if not pending:
            return
        await db.flush()  # 拿到 kp.id
        for node, kp in pending:
            node.kp_id = kp.id

    async def _link_nodes_to_curriculum(
        self, db: AsyncSession, proj: Project,
        nodes_meta: list[dict], title_to_node: dict[str, ProjectTreeNode],
    ) -> None:
        """树节点生成后，尝试按 subject + 标题关键词匹配课程章节，补 curriculum_chapter_id。"""
        if not proj.subject:
            return
        from app.models.curriculum import CurriculumChapter
        chapters_q = await db.execute(
            select(CurriculumChapter).where(CurriculumChapter.subject == proj.subject).limit(50)
        )
        chapters = list(chapters_q.scalars().all())
        if not chapters:
            return
        chapter_titles = {c.lesson_title: c for c in chapters}
        # 扩展：也按 chapter_title 匹配
        for c in chapters:
            chapter_titles[c.chapter_title] = c

        for nmeta in nodes_meta:
            node_title = str(nmeta.get("title", ""))
            node = title_to_node.get(node_title)
            if not node or node.curriculum_chapter_id:
                continue
            # 直接匹配
            if node_title in chapter_titles:
                node.curriculum_chapter_id = chapter_titles[node_title].id
                continue
            # 关键词包含匹配
            for ct, chapter in chapter_titles.items():
                if len(node_title) >= 3 and (node_title[:3] in ct or ct[:3] in node_title):
                    node.curriculum_chapter_id = chapter.id
                    break

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
