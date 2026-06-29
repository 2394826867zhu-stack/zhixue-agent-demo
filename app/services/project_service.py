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
    ProjectDataSummary, FrameworkPreviewNode, ProjectDraftExtraction,
)
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.llm.client import LLMClient
from app.llm.prompts.project_init import (
    SYSTEM_PROJECT_DRAFT, PROJECT_DRAFT_FROM_DIALOG, SYSTEM_DRAFT_EXTRACT, DRAFT_EXTRACT,
)
from app.services.framework_service import generate_framework, validate_framework
from app.services import subject_taxonomy
from app.services import feasibility_service
from app.services.learner_state_service import mastery_threshold

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


_PREVIEW_DIFFS = {"blue", "purple", "gold"}


def _framework_to_preview(framework: dict) -> tuple[list[FrameworkPreviewNode], dict]:
    """框架 dict → (framework_preview 章节/课时列表, tree_summary 难度计数)。INC-E。"""
    nodes: list[FrameworkPreviewNode] = []
    blue = purple = gold = 0
    for ch in framework.get("chapters", []):
        if not isinstance(ch, dict):
            continue
        lessons_out = []
        for ls in ch.get("lessons", []) or []:
            if not isinstance(ls, dict) or not str(ls.get("title", "")).strip():
                continue
            d = ls.get("difficulty") if ls.get("difficulty") in _PREVIEW_DIFFS else "blue"
            lessons_out.append({
                "title": str(ls.get("title", "")),
                "kp_names": list(ls.get("kp_names", []) or []),
                "difficulty": d,
            })
            if d == "blue":
                blue += 1
            elif d == "purple":
                purple += 1
            else:
                gold += 1
        nodes.append(FrameworkPreviewNode(
            chapter_title=str(ch.get("title", "")),
            phase_name=str(ch.get("phase_name", "")),
            lessons=lessons_out,
        ))
    summary = {"total_nodes": blue + purple + gold,
               "blue_count": blue, "purple_count": purple, "gold_count": gold}
    return nodes, summary


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
            # v3 intake 字段（INC-E：快路径也持久化，/tree/generate 据此富化生成）
            goal_type=data.goal_type, goal_spec=data.goal_spec,
            starting_mode=data.starting_mode, starting_payload=data.starting_payload,
            prior_knowledge_strategy=data.prior_knowledge_strategy,
            mastery_depth=data.mastery_depth, scope_mode=data.scope_mode,
            scope_topics=list(data.scope_topics or []),
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
        """INC-E：/preview → 跑 F1 生成真框架 + 可行性 → preview card（不入库）。

        框架缓存进 card.framework_json，供 /confirm 据此建树（不重生成）。这是 ~30s 加载窗
        （D9 两段确认的第一段）。生成失败 → framework_preview 空（前端检测 → 重试）。
        """
        rem_weeks = feasibility_service.remaining_weeks(draft.target_completion_date, default=12)
        # 生成前粗估 → feasibility_advice 注入 F1
        pre_feas = feasibility_service.estimate_feasibility(
            estimated_hours=feasibility_service.estimate_hours_rough(
                feasibility_service.estimate_node_count(
                    draft.goal_type, draft.scope_mode, draft.mastery_depth),
                draft.mastery_depth),
            weekly_hours=draft.weekly_hours, remaining_weeks_val=rem_weeks)
        framework = await generate_framework(
            name=draft.name, subject=draft.subject, summary=draft.summary,
            weeks=int(rem_weeks), user_id=user_id,
            goal_type=draft.goal_type, mastery_depth=draft.mastery_depth,
            domain_template=subject_taxonomy.domain_template_for(draft.subject),
            scope_mode=draft.scope_mode, scope_topics=list(draft.scope_topics or []),
            feasibility_advice=feasibility_service.feasibility_advice_for_prompt(pre_feas["band"]),
        )
        if framework and framework.get("chapters"):
            preview_nodes, tree_summary = _framework_to_preview(framework)
            est_hours = feasibility_service.estimate_hours_from_counts(
                tree_summary["blue_count"], tree_summary["purple_count"], tree_summary["gold_count"])
            phases = [
                {"name": str(p.get("name", "")), "description": str(p.get("description", "")),
                 "est_weeks": max(1, int(p.get("weeks", 4) or 4))}
                for p in framework.get("phases", [])
                if isinstance(p, dict) and str(p.get("name", "")).strip()
            ]
        else:
            # 生成失败：空框架（前端检测 framework_preview 空 → 重试），phases 退调性模板供展示
            framework = {}
            preview_nodes, tree_summary = [], {"total_nodes": 0, "blue_count": 0, "purple_count": 0, "gold_count": 0}
            est_hours = 0.0
            tone = _detect_tone(draft.subject, "user_project", draft.summary)
            phases = [{"name": n, "description": d, "est_weeks": max(1, round(days / 7))}
                      for n, d, days in _build_phases_for_tone(tone)]
        feas = feasibility_service.estimate_feasibility(
            estimated_hours=est_hours, weekly_hours=draft.weekly_hours, remaining_weeks_val=rem_weeks)
        milestones = []
        if draft.target_completion_date:
            milestones.append({
                "title": "项目截止", "type": "deadline",
                "days_from_now": (draft.target_completion_date - datetime.now(timezone.utc)).days,
            })
        return ProjectPreviewCard(
            draft=draft,
            proposed_phases=phases,
            proposed_milestones=milestones,
            proposed_tree_summary=tree_summary,
            estimated_total_hours=round(est_hours or (draft.weekly_hours or 5) * 6, 1),
            framework_preview=preview_nodes,
            framework_json=framework,
            feasibility=feas,
        )

    async def confirm_preview(
        self, db: AsyncSession, user_id: str, req: ProjectConfirmRequest,
    ) -> Project:
        """INC-E：用户确认 → 落库 project（全 v3 字段）+ 从缓存框架建树（不重 LLM）。

        framework_json 在 → _build_tree_from_framework（建 phases + 树 + 先修边，advisory lock
        防双确认重复，H1）；无 → 退调性 phases + framework_status=failed（preview 生成失败仍确认时，
        供 /tree/generate 重试）。PRD 行 339 全面初始化在此一次完成（不再解耦到 /tree/generate）。
        """
        uid = uuid.UUID(user_id)
        card = req.preview
        draft = card.draft

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
            # v3 intake 字段（INC-E）
            goal_type=draft.goal_type, goal_spec=draft.goal_spec,
            starting_mode=draft.starting_mode, starting_payload=draft.starting_payload,
            prior_knowledge_strategy=draft.prior_knowledge_strategy,
            mastery_depth=draft.mastery_depth, scope_mode=draft.scope_mode,
            scope_topics=list(draft.scope_topics or []),
        )
        db.add(proj)
        await db.flush()  # 拿到 proj.id

        now = datetime.now(timezone.utc)
        # milestones（不依赖框架）
        # P1-12：milestone 来自 LLM/客户端回传，字段可能缺失或畸形——全部用 .get 兜底，
        # 缺 title 的项跳过、days_from_now 非数回退 30，避免单条畸形导致 confirm 整体 500。
        for m in card.proposed_milestones:
            if not isinstance(m, dict):
                continue
            title = (m.get("title") or "").strip()
            if not title:
                continue
            try:
                days = int(m.get("days_from_now", 30))
            except (TypeError, ValueError):
                days = 30
            event = now + timedelta(days=days)
            db.add(ProjectMilestone(
                project_id=proj.id,
                title=title,
                description=m.get("description", ""),
                milestone_type=m.get("type", "custom"),
                event_date=event,
            ))

        framework = card.framework_json or {}
        # P0-2：confirm 不能盲信客户端回传的 framework_json——F1 的 validate_framework
        # (规模/反扁平占位闸) 只在 generate 路径跑，confirm 必须复跑同一校验，否则可被
        # 构造任意框架绕过结构防线。校验不过 → 退 phases 兜底路径(不建脏树)。
        if framework.get("chapters") and validate_framework(framework):
            # advisory lock 防双确认重复建树（H1）
            lock_key = int(hashlib.md5(f"tree:{proj.id}".encode()).hexdigest()[:8], 16) % (2**31)
            await db.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))
            # 从缓存框架建 phases + 树 + 先修边（不重 LLM）
            await self._build_tree_from_framework(db, proj, framework)
            # INC-F：prior_knowledge 播种（mastered_chapter_ids → status/p_mastery）后续补
            proj.framework_status = "ready"
        else:
            # 无缓存框架（NL/onboarding 路径，或 preview 生成失败仍确认），或框架校验不过 →
            # 退调性 phases，树延后。**不强制 failed**：保持旧 ready 默认（onboarding D10 不在本轮改），
            # 树由 /tree/generate 建（该路径 generate 失败时才置 failed，见 generate_tree_nodes）。
            cursor = now
            for idx, p in enumerate(card.proposed_phases):
                if not isinstance(p, dict):
                    continue
                pname = (p.get("name") or "").strip()
                if not pname:
                    continue
                try:
                    weeks = int(p.get("est_weeks", 2))
                except (TypeError, ValueError):
                    weeks = 2
                end = cursor + timedelta(weeks=weeks)
                db.add(ProjectPhase(
                    project_id=proj.id, name=pname[:60], description=str(p.get("description", ""))[:500],
                    start_date=cursor, end_date=end, sort_order=idx, is_current=(idx == 0),
                ))
                cursor = end

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

    async def extract_draft_fields(
        self, db: AsyncSession, user_id: str, dialog: str,
    ) -> ProjectDraftExtraction:
        """INC-I：一句话 NL → 带置信度字段（预填漏斗）。**只提取不创建**（spec §11.6）。

        安全规则在 prompt 强制（保守 goal_type / 日期不推断 / subject 映射）；置信门控在前端。
        空输入 / 提取失败 → 空 fields + warning（200 兜底，绝不 500，对齐冷启动诚实兜底）。
        """
        if not dialog or not dialog.strip():
            return ProjectDraftExtraction(fields={}, warnings=[])
        llm = LLMClient()
        prompt = DRAFT_EXTRACT.format(dialog=dialog[:1000])
        try:
            raw = await llm.generate(
                prompt=prompt, system=SYSTEM_DRAFT_EXTRACT,
                user_id=user_id, endpoint="project.extract_fields",
            )
            data = _extract_json(raw)
            fields = data.get("fields") if isinstance(data, dict) else None
            warnings = data.get("warnings") if isinstance(data, dict) else None
            return ProjectDraftExtraction(
                fields=fields if isinstance(fields, dict) else {},
                warnings=warnings if isinstance(warnings, list) else [],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("extract_draft_fields failed: %s", e)
            return ProjectDraftExtraction(fields={}, warnings=["无法从输入中识别学习目标，请手动填写"])

    # ── LLM 驱动 · 生成树节点 ───────────────────────────────────────────

    async def generate_tree_nodes(
        self, db: AsyncSession, project_id: str, user_id: str, rebuild: bool = False,
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

        if rebuild:
            # INC-J「重建框架」：清旧树 + 项目生成的 KP（级联其闪卡/错题/先修边 ondelete=CASCADE）
            # → 重新生成。破坏性（重置进度），前端走二次确认弹窗。intake 字段锁定不变 = 重 roll LLM。
            from app.models.knowledge_point import KnowledgePoint
            await db.execute(delete(ProjectTreeNode).where(ProjectTreeNode.project_id == proj.id))
            await db.execute(delete(KnowledgePoint).where(
                KnowledgePoint.project_id == proj.id,
                KnowledgePoint.notebook_origin == "user_project",
            ))
            await db.flush()
            proj.framework_status = "building"

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
        # INC-D 可行性：生成前粗估节点数/耗时 → 注入 prompt 调深度（soft，不拦截）
        _feas = feasibility_service.estimate_feasibility(
            estimated_hours=feasibility_service.estimate_hours_rough(
                feasibility_service.estimate_node_count(
                    proj.goal_type, proj.scope_mode, proj.mastery_depth),
                proj.mastery_depth,
            ),
            weekly_hours=proj.weekly_hours,
            remaining_weeks_val=feasibility_service.remaining_weeks(
                proj.target_completion_date, default=total_weeks),
        )
        framework = await generate_framework(
            name=proj.name, subject=proj.subject, summary=proj.summary,
            weeks=total_weeks, user_id=user_id,
            # INC-C：goal_type / mastery_depth / 领域骨架 / scope 注入富化生成
            goal_type=proj.goal_type, mastery_depth=proj.mastery_depth,
            domain_template=subject_taxonomy.domain_template_for(proj.subject),
            scope_mode=proj.scope_mode, scope_topics=list(proj.scope_topics or []),
            feasibility_advice=feasibility_service.feasibility_advice_for_prompt(_feas["band"]),  # INC-D
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
        _DIFF_RANK = {"blue": 0, "purple": 1, "gold": 2}
        # P0-2：框架来源可能是客户端回传 → 必须钳制规模，防超大写入（DoS/数据膨胀）。
        _MAX_CHAPTERS = 50
        _MAX_LESSONS = 50
        # P0-2：KnowledgePoint.subject 列宽仅 String(50)，而 Project.subject 已扩到 80；
        # 若不截断，>50 字符 subject 会让建树事务整体 500 回滚。
        kp_subject = str(proj.subject)[:50] if proj.subject else None

        def _valid_diff(v):
            return v if isinstance(v, str) and v in _DIFF_RANK else None

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
            # P2-3：缺难度兜底——按阶段序号给 blue→purple 渐进，但**封顶 purple 不到 gold**。
            # 原 min(sort_order,2) 让第 3+ 阶段所有缺难度课时一律 gold，违背 surface「不出金」；
            # gold 只应来自 LLM 每课显式 difficulty，不由阶段序号臆断。
            ph = phase_lookup.get(phase_name or "")
            return _DIFF[min(ph.sort_order, 1)] if ph else "blue"

        # 2. 根节点
        root = ProjectTreeNode(
            project_id=proj.id, parent_id=None, depth=0,
            phase_id=(default_phase.id if default_phase else None),
            title=proj.name[:120], difficulty="blue", importance=3,
            is_on_main_path=True, status="available", sort_order=0,
        )
        db.add(root)
        await db.flush()

        # INC-F 先验知识播种准备：by_self_report 勾掌握的章节 → 按 strategy 播种节点 + KP（喂 L2）
        mastered_titles: set[str] = set()
        strategy = proj.prior_knowledge_strategy or "review"
        if proj.starting_mode == "by_self_report":
            mastered_titles = {
                str(t).strip()
                for t in (proj.starting_payload or {}).get("mastered_chapter_ids", [])
                if str(t).strip()
            }
        _thr = mastery_threshold(proj.mastery_depth)   # 项目掌握线（按深度，spec §5.2）
        skip_pm = round(max(0.85, _thr), 2)            # skip：至少清掌握线
        review_pm = round(max(0.6, _thr - 0.15), 2)    # review：略低于掌握线，需复习巩固

        # 3. 大章节(depth1) > 小课时(depth2) + 每课 KP（难度取 LLM 每课返回值，INC-C）
        node_count = 1
        sort = 1
        lesson_kp_ids: list[uuid.UUID] = []        # 课时顺序 → 先修兜底链
        kp_name_to_id: dict[str, uuid.UUID] = {}   # 课时名 / kp_name → kp_id（先修边解析）
        for ch in (framework.get("chapters", []) or [])[:_MAX_CHAPTERS]:
            if not isinstance(ch, dict) or not str(ch.get("title", "")).strip():
                continue
            ph = phase_lookup.get(ch.get("phase_name")) or default_phase
            phase_diff = _diff_for(ch.get("phase_name"))  # 缺失难度的兜底
            raw_lessons = [ls for ls in (ch.get("lessons", []) or [])
                           if isinstance(ls, dict) and str(ls.get("title", "")).strip()][:_MAX_LESSONS]
            lesson_diffs = [_valid_diff(ls.get("difficulty")) or phase_diff for ls in raw_lessons]
            # 章节(容器)难度 = 其课时里最高难度（无则 phase 兜底）
            chap_diff = max(lesson_diffs, key=lambda d: _DIFF_RANK[d]) if lesson_diffs else phase_diff
            chap = ProjectTreeNode(
                project_id=proj.id, parent_id=root.id, depth=1,
                phase_id=(ph.id if ph else None), title=str(ch["title"])[:120],
                difficulty=chap_diff, importance=2, is_on_main_path=True,
                status="available", sort_order=sort,  # 章节是容器，恒 available
            )
            db.add(chap)
            await db.flush()
            node_count += 1
            sort += 1
            ch_mastered = str(ch["title"]).strip() in mastered_titles
            for ls, ls_diff in zip(raw_lessons, lesson_diffs):
                optional = bool(ls.get("optional", False))
                # INC-F：勾掌握章节按 strategy 播种（skip→completed / review→available + p_mastery 种子）
                if ch_mastered and strategy == "skip":
                    kp_status, kp_pm = "mastered", skip_pm
                    ls_status, ls_comp, ls_mast = "completed", 1.0, skip_pm
                elif ch_mastered:
                    kp_status, kp_pm = "reviewing", review_pm
                    ls_status, ls_comp, ls_mast = "available", 0.0, review_pm
                else:
                    kp_status, kp_pm = "new", None
                    ls_status, ls_comp, ls_mast = "locked", 0.0, 0.0
                kp = KnowledgePoint(
                    user_id=proj.user_id, project_id=proj.id,
                    name=str(ls["title"])[:255], subject=kp_subject,
                    difficulty_tier=ls_diff, mastery_status=kp_status, p_mastery=kp_pm,
                    notebook_origin="user_project",
                )
                db.add(kp)
                await db.flush()
                lesson = ProjectTreeNode(
                    project_id=proj.id, parent_id=chap.id, depth=2,
                    phase_id=(ph.id if ph else None), kp_id=kp.id,
                    title=str(ls["title"])[:120], difficulty=ls_diff, importance=1,
                    is_on_main_path=(not optional),  # optional 课时移出主干高亮
                    status=ls_status, completion_pct=ls_comp, mastery_pct=ls_mast,
                    sort_order=sort,
                    completed_at=(datetime.now(timezone.utc) if ls_status == "completed" else None),
                )
                db.add(lesson)
                node_count += 1
                sort += 1
                lesson_kp_ids.append(kp.id)
                # 先修解析映射：课时名 + 该课所有 kp_names → 此 kp_id
                kp_name_to_id[str(ls["title"]).strip()] = kp.id
                for n in ls.get("kp_names", []) or []:
                    if isinstance(n, str) and n.strip():
                        kp_name_to_id.setdefault(n.strip(), kp.id)
        await db.flush()

        # 4. 确保至少一节可学：解锁首个仍 locked 的课时（INC-F seeded 的 completed/available 保留）
        if lesson_kp_ids:
            first_locked = (await db.execute(
                select(ProjectTreeNode)
                .where(ProjectTreeNode.project_id == proj.id, ProjectTreeNode.depth == 2,
                       ProjectTreeNode.status == "locked")
                .order_by(ProjectTreeNode.sort_order.asc()).limit(1)
            )).scalar_one_or_none()
            if first_locked:
                first_locked.status = "available"

        # 5. 先修边：优先框架 prereqs[]（真依赖，KP 名对 → kp_id）；无可解析则退顺序链兜底。
        #    给内核 frontier 真依赖链（F4 据此驱动解锁，替代纯 sort_order）。
        edge_pairs: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for pr in framework.get("prereqs", []) or []:
            if not (isinstance(pr, (list, tuple)) and len(pr) == 2):
                continue
            a_id = kp_name_to_id.get(str(pr[0]).strip())
            b_id = kp_name_to_id.get(str(pr[1]).strip())
            # 去自环 + 去 2-环（a→b 已在则不再加 b→a）
            if a_id and b_id and a_id != b_id and (b_id, a_id) not in edge_pairs:
                edge_pairs.add((a_id, b_id))
        if not edge_pairs:  # 框架无可解析先修 → 顺序链兜底（至少给内核一条依赖链）
            edge_pairs = {(a, b) for a, b in zip(lesson_kp_ids, lesson_kp_ids[1:])}
        for a_id, b_id in edge_pairs:
            db.add(PrerequisiteEdge(user_id=proj.user_id, from_kp_id=a_id, to_kp_id=b_id,
                                    confidence=0.6, source="llm"))

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
