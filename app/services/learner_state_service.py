"""学习内核 P1 · 学习者状态聚合（learner_state_service）。

把图谱（先修边 + 掌握度）、待复习、考试倒计时聚合成单一状态对象，
作为 P2 决策策略（learning_engine）的输入接口。P1 只产出状态，不做决策。

退化兜底：无 KP / 无边 / 无考试 → 返回零值结构，绝不崩（设计§1.3）。
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_point import KnowledgePoint
from app.models.flashcard import Flashcard
from app.models.exam import Exam
from app.models.prerequisite_edge import PrerequisiteEdge
from app.services import graph_service

logger = logging.getLogger(__name__)

_MASTERED_THRESHOLD = 0.6  # 与 graph_service.learnable_frontier 默认一致
_TRANSFER_THRESHOLD = 0.8  # G-P3-4 掌握度达此阈 → 迁移挑战候选（与 learning_engine 一致）


async def get_learner_state(db: AsyncSession, user_id: str) -> dict:
    """聚合学习者状态：知识图谱 + 待复习 + 考试 + streak。"""
    uid = uuid.UUID(user_id)
    today = date.today()

    # ---- 知识图谱（节点掌握度 + 先修边 → 前沿）----
    kp_rows = await db.execute(
        select(
            KnowledgePoint.id, KnowledgePoint.name,
            KnowledgePoint.p_mastery, KnowledgePoint.mastery_status,
        ).where(KnowledgePoint.user_id == uid)
    )
    mastery: dict[str, float] = {}
    id_to_name: dict[str, str] = {}
    for kid, name, pm, status in kp_rows.all():
        sid = str(kid)
        mastery[sid] = graph_service.mastery_value(pm, status)
        id_to_name[sid] = name

    total = len(mastery)
    mastered = sum(1 for v in mastery.values() if v >= _MASTERED_THRESHOLD)
    learning = total - mastered

    edge_rows = await db.execute(
        select(PrerequisiteEdge.from_kp_id, PrerequisiteEdge.to_kp_id).where(
            PrerequisiteEdge.user_id == uid
        )
    )
    edges = [(str(f), str(t)) for f, t in edge_rows.all()]

    frontier_ids = graph_service.learnable_frontier(mastery, edges)
    frontier_ids.sort(key=lambda i: mastery.get(i, 0.0))
    frontier = [
        {"id": fid, "name": id_to_name.get(fid, ""),
         "p_mastery": round(mastery.get(fid, 0.0), 3),
         # P3 先修杠杆：下游可达数（gain_policy 用；图谱无边时为 0，gain 兜底）
         "downstream_count": graph_service.downstream_count(fid, edges)}
        for fid in frontier_ids[:10]
    ]

    # ---- P3 G-P3-4：已掌握待迁移验证的节点（掌握度高 → 换皮新题测真懂）----
    # 注：迁移探针去重（last_probe 近期已迁移过则跳过）待 P4 真实探针回流接入。
    transfer_candidates = [
        {"id": sid, "name": id_to_name.get(sid, ""), "p_mastery": round(v, 3)}
        for sid, v in sorted(mastery.items(), key=lambda kv: kv[1], reverse=True)
        if v >= _TRANSFER_THRESHOLD
    ][:5]

    # ---- 待复习闪卡 ----
    due = await db.execute(
        select(func.count(Flashcard.id)).where(
            and_(Flashcard.user_id == uid, Flashcard.due_date <= today)
        )
    )
    due_count = due.scalar() or 0

    # ---- 考试倒计时 ----
    exam_rows = await db.execute(
        select(Exam).where(
            and_(Exam.user_id == uid, Exam.exam_date >= today)
        ).order_by(Exam.exam_date).limit(1)
    )
    next_exam = exam_rows.scalars().first()
    if next_exam is not None and next_exam.exam_date is not None:
        ed = next_exam.exam_date
        ed = ed.date() if hasattr(ed, "date") else ed  # exam_date 是 datetime，规范到 date 再相减
        days_left = (ed - today).days
        exams_block = {
            "next": {"subject": next_exam.subject, "name": next_exam.name,
                     "days_left": days_left},
            "stress_level": "high" if days_left <= 3 else ("moderate" if days_left <= 14 else "low"),
        }
    else:
        next_exam = None
        exams_block = {"next": None, "stress_level": "low"}

    # ---- streak（连续学习天数，best-effort）----
    streak = await _study_streak(db, uid, today)

    return {
        "knowledge_graph": {
            "total": total,
            "mastered": mastered,
            "learning": learning,
            "frontier": frontier,
            "transfer_candidates": transfer_candidates,
        },
        "review_due": {"due": due_count},
        "exams": exams_block,
        "streak": streak,
    }


async def _study_streak(db: AsyncSession, uid: uuid.UUID, today: date) -> int:
    """连续到今天（或昨天）有已完成每日任务的天数。无数据 → 0。失败 → 0。"""
    try:
        from datetime import timedelta
        from app.models.task import DailyTask

        rows = await db.execute(
            select(DailyTask.task_date).where(
                and_(DailyTask.user_id == uid, DailyTask.is_done.is_(True))
            ).distinct()
        )
        done_days = {r for (r,) in rows.all()}
        if not done_days:
            return 0
        # 从今天往回数连续天；允许从昨天起算（今天还没学不清零）
        anchor = today if today in done_days else today - timedelta(days=1)
        streak = 0
        cur = anchor
        while cur in done_days:
            streak += 1
            cur = cur - timedelta(days=1)
        return streak
    except Exception:  # noqa: BLE001
        logger.exception("study streak calc failed uid=%s", uid)
        return 0
