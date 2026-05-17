import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.path import PathStage, PathNode
from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingQuestion
from app.models.task import PomodoroRecord
from app.schemas.path import PathGenerateRequest, PathNodeCreate, PathStageCreate
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError

logger = logging.getLogger(__name__)


class PathService:

    # ── 查询 ──────────────────────────────────────────────────────────────

    async def get_stages(self, db: AsyncSession, user_id: str) -> list[PathStage]:
        uid = uuid.UUID(user_id)
        result = await db.execute(
            select(PathStage)
            .where(PathStage.user_id == uid)
            .order_by(PathStage.sort_order.asc())
        )
        stages = list(result.scalars().unique().all())
        # eager-load nodes for each stage
        for stage in stages:
            await db.refresh(stage, ["nodes"])
        return stages

    async def get_coach_tip(self, db: AsyncSession, user_id: str) -> dict:
        uid = uuid.UUID(user_id)

        # current/in-progress nodes
        current_result = await db.execute(
            select(PathNode)
            .where(PathNode.user_id == uid, PathNode.status == "current")
            .order_by(PathNode.sort_order.asc())
            .limit(1)
        )
        current_node = current_result.scalar_one_or_none()

        counts_result = await db.execute(
            select(
                func.count().label("total"),
                func.count(PathNode.id).filter(PathNode.status == "done").label("done"),
            ).where(PathNode.user_id == uid)
        )
        counts = counts_result.one()
        total = counts[0] or 0
        done = counts[1] or 0
        progress_pct = round(done / total * 100) if total else 0

        # weak subjects from training
        weak_rows = await db.execute(
            select(KnowledgePoint.subject, func.count(TrainingQuestion.id))
            .join(TrainingQuestion, TrainingQuestion.knowledge_point_id == KnowledgePoint.id)
            .where(
                TrainingQuestion.user_id == uid,
                TrainingQuestion.is_wrong == True,
                TrainingQuestion.is_retry == False,
                KnowledgePoint.subject.isnot(None),
            )
            .group_by(KnowledgePoint.subject)
            .order_by(func.count(TrainingQuestion.id).desc())
            .limit(2)
        )
        weak_subjects = [r[0] for r in weak_rows]

        # streak
        from datetime import date, timedelta
        today = date.today()
        streak_dates = await db.execute(
            select(PomodoroRecord.record_date)
            .where(
                PomodoroRecord.user_id == uid,
                PomodoroRecord.record_date >= today - timedelta(days=30),
            )
            .distinct()
        )
        dates_set = {r[0] for r in streak_dates}
        streak = 0
        d = today
        while d in dates_set:
            streak += 1
            d -= timedelta(days=1)

        tip = await self._generate_coach_tip(
            current_node=current_node.title if current_node else None,
            done_count=done,
            total_count=total,
            progress_pct=progress_pct,
            weak_subjects=weak_subjects,
            streak_days=streak,
        )

        return {
            "message": tip["message"],
            "suggested_node_id": current_node.id if current_node else None,
            "suggested_action": tip.get("suggested_action", "continue"),
        }

    # ── 完成节点 ──────────────────────────────────────────────────────────

    async def complete_node(self, db: AsyncSession, node_id: str, user_id: str) -> PathNode:
        node = await self._get_node(db, node_id, user_id)
        if node.status == "done":
            return node

        node.status = "done"
        node.completed_at = datetime.now(timezone.utc)

        # unlock next nodes in the same stage that have this as their only prerequisite
        await self._unlock_dependents(db, uuid.UUID(user_id), node.id, node.stage_id)

        await db.commit()
        await db.refresh(node)
        return node

    # ── AI 生成 ───────────────────────────────────────────────────────────

    async def ai_generate(self, db: AsyncSession, user_id: str, body: PathGenerateRequest) -> list[PathStage]:
        uid = uuid.UUID(user_id)

        # collect user context
        subject_rows = await db.execute(
            select(KnowledgePoint.subject, func.count(), func.count(KnowledgePoint.id).filter(KnowledgePoint.mastery_status == "mastered"))
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.subject)
        )
        subject_data = [(r[0] or "未分类", r[1], r[2]) for r in subject_rows]
        subject_summary = "; ".join(f"{s}({total}个KP, 已掌握{mastered})" for s, total, mastered in subject_data) or "暂无"

        mastery_rows = await db.execute(
            select(KnowledgePoint.mastery_status, func.count())
            .where(KnowledgePoint.user_id == uid)
            .group_by(KnowledgePoint.mastery_status)
        )
        dist = {r[0]: r[1] for r in mastery_rows}
        mastery_summary = f"新建{dist.get('new', 0)}/学习中{dist.get('learning', 0)}/复习{dist.get('reviewing', 0)}/已掌握{dist.get('mastered', 0)}"

        weak_kp_rows = await db.execute(
            select(KnowledgePoint.name, KnowledgePoint.subject)
            .where(KnowledgePoint.user_id == uid, KnowledgePoint.mastery_status.in_(["new", "learning"]))
            .order_by(KnowledgePoint.updated_at.asc())
            .limit(5)
        )
        weak_kps = ", ".join(f"{r[0]}({r[1] or '?'})" for r in weak_kp_rows) or "暂无"

        raw_stages = await self._call_llm_generate(
            subject_summary=subject_summary,
            mastery_summary=mastery_summary,
            weak_kps=weak_kps,
            goal=body.goal or "全面提升各科学习效率",
        )

        # delete existing AI-generated stages
        existing = await db.execute(
            select(PathStage).where(PathStage.user_id == uid, PathStage.is_ai_generated == True)
        )
        for old_stage in existing.scalars().all():
            await db.delete(old_stage)

        # create new stages + nodes
        stages = []
        for i, stage_data in enumerate(raw_stages):
            stage = PathStage(
                user_id=uid,
                title=stage_data["title"],
                description=stage_data.get("description", ""),
                sort_order=i,
                is_ai_generated=True,
            )
            db.add(stage)
            await db.flush()  # get stage.id

            for j, node_data in enumerate(stage_data.get("nodes", [])):
                # first node of first stage is "current", rest locked
                status = "current" if (i == 0 and j == 0) else "locked"
                node = PathNode(
                    user_id=uid,
                    stage_id=stage.id,
                    title=node_data["title"],
                    node_type=node_data.get("node_type", "lesson"),
                    status=status,
                    subject=node_data.get("subject"),
                    estimated_minutes=int(node_data.get("estimated_minutes", 30)),
                    reward=node_data.get("reward"),
                    sort_order=j,
                )
                db.add(node)
            stages.append(stage)

        await db.commit()
        for stage in stages:
            await db.refresh(stage, ["nodes"])
        return stages

    # ── 手动管理 ──────────────────────────────────────────────────────────

    async def create_stage(self, db: AsyncSession, user_id: str, body: PathStageCreate) -> PathStage:
        uid = uuid.UUID(user_id)
        max_order = await db.execute(
            select(func.max(PathStage.sort_order)).where(PathStage.user_id == uid)
        )
        stage = PathStage(
            user_id=uid,
            title=body.title,
            description=body.description,
            sort_order=(max_order.scalar() or 0) + 1,
        )
        db.add(stage)
        await db.commit()
        await db.refresh(stage, ["nodes"])
        return stage

    async def create_node(self, db: AsyncSession, user_id: str, body: PathNodeCreate) -> PathNode:
        uid = uuid.UUID(user_id)
        stage = await self._get_stage(db, body.stage_id, user_id)
        max_order = await db.execute(
            select(func.max(PathNode.sort_order)).where(PathNode.stage_id == stage.id)
        )
        node = PathNode(
            user_id=uid,
            stage_id=stage.id,
            title=body.title,
            node_type=body.node_type,
            status="locked",
            subject=body.subject,
            estimated_minutes=body.estimated_minutes,
            reward=body.reward,
            note_id=uuid.UUID(body.note_id) if body.note_id else None,
            kp_ids=[uuid.UUID(k) for k in body.kp_ids],
            prerequisite_ids=[uuid.UUID(p) for p in body.prerequisite_ids],
            sort_order=(max_order.scalar() or 0) + 1,
        )
        db.add(node)
        await db.commit()
        await db.refresh(node)
        return node

    # ── 内部方法 ──────────────────────────────────────────────────────────

    async def _unlock_dependents(
        self, db: AsyncSession, uid: uuid.UUID,
        completed_node_id: uuid.UUID, stage_id: uuid.UUID
    ) -> None:
        siblings = await db.execute(
            select(PathNode).where(
                PathNode.stage_id == stage_id,
                PathNode.status == "locked",
            )
        )
        for node in siblings.scalars().all():
            if not node.prerequisite_ids:
                # no prerequisites → unlock automatically if previous done
                pass
            elif completed_node_id in node.prerequisite_ids:
                # check all prerequisites are done
                prereqs = await db.execute(
                    select(PathNode.status).where(PathNode.id.in_(node.prerequisite_ids))
                )
                if all(r[0] == "done" for r in prereqs):
                    node.status = "current"

    async def _get_stage(self, db: AsyncSession, stage_id: str, user_id: str) -> PathStage:
        result = await db.execute(select(PathStage).where(PathStage.id == uuid.UUID(stage_id)))
        stage = result.scalar_one_or_none()
        if not stage:
            raise NotFoundError("学习阶段")
        if str(stage.user_id) != user_id:
            raise PermissionDeniedError()
        return stage

    async def _get_node(self, db: AsyncSession, node_id: str, user_id: str) -> PathNode:
        result = await db.execute(select(PathNode).where(PathNode.id == uuid.UUID(node_id)))
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundError("路径节点")
        if str(node.user_id) != user_id:
            raise PermissionDeniedError()
        return node

    async def _call_llm_generate(
        self, subject_summary: str, mastery_summary: str, weak_kps: str, goal: str
    ) -> list[dict]:
        from app.llm.client import llm_client
        from app.llm.prompts.path_prompts import PATH_GENERATE_PROMPT, SYSTEM_PATH

        try:
            raw = await llm_client.generate(
                PATH_GENERATE_PROMPT.format(
                    subject_summary=subject_summary,
                    mastery_summary=mastery_summary,
                    weak_kps=weak_kps,
                    goal=goal,
                ),
                system=SYSTEM_PATH,
            )
            data = _parse_json_safe(raw)
            if isinstance(data, list) and data:
                return data
            raise ValueError("LLM 返回格式不符")
        except Exception as e:
            logger.warning(f"Path generation LLM failed: {e}, using fallback")
            return _fallback_stages()

    async def _generate_coach_tip(
        self, current_node: str | None, done_count: int,
        total_count: int, progress_pct: int,
        weak_subjects: list[str], streak_days: int,
    ) -> dict:
        from app.llm.client import llm_client
        from app.llm.prompts.path_prompts import COACH_TIP_PROMPT, SYSTEM_PATH

        try:
            raw = await llm_client.generate(
                COACH_TIP_PROMPT.format(
                    current_node=current_node or "暂无进行中节点",
                    done_count=done_count,
                    total_count=total_count,
                    progress_pct=progress_pct,
                    weak_subjects="、".join(weak_subjects) if weak_subjects else "暂无",
                    streak_days=streak_days,
                ),
                system=SYSTEM_PATH,
            )
            return _parse_json_safe(raw) or _fallback_tip(current_node, weak_subjects)
        except Exception as e:
            logger.warning(f"Coach tip LLM failed: {e}")
            return _fallback_tip(current_node, weak_subjects)


def _parse_json_safe(text: str) -> list | dict | None:
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception:
        return None


def _fallback_stages() -> list[dict]:
    return [
        {
            "title": "打好基础",
            "description": "先夯实各科基础知识点，建立稳固的知识框架",
            "nodes": [
                {"title": "整理本周笔记", "node_type": "lesson", "subject": None, "estimated_minutes": 30, "reward": None},
                {"title": "刷新到期闪卡", "node_type": "review", "subject": None, "estimated_minutes": 20, "reward": None},
                {"title": "完成错题重练", "node_type": "training", "subject": None, "estimated_minutes": 25, "reward": "错题突破者"},
            ],
        },
        {
            "title": "强化练习",
            "description": "针对薄弱知识点做专项训练，提升应用能力",
            "nodes": [
                {"title": "专项训练（应用层）", "node_type": "training", "subject": None, "estimated_minutes": 30, "reward": None},
                {"title": "归纳总结报告", "node_type": "project", "subject": None, "estimated_minutes": 40, "reward": "学习达人"},
            ],
        },
    ]


def _fallback_tip(current_node: str | None, weak_subjects: list[str]) -> dict:
    if current_node:
        return {"message": f'继续完成"{current_node}"，保持当前节奏！', "suggested_action": "continue"}
    if weak_subjects:
        return {"message": f"建议优先复习{weak_subjects[0]}，从错题入手效果最好。", "suggested_action": "review"}
    return {"message": "今天可以先生成一份学习路径，让 AI 帮你规划接下来的学习顺序。", "suggested_action": "start"}


path_service = PathService()
