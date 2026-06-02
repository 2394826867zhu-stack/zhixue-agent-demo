"""G-P4-2 · 外部成绩锚服务：把录入的真实考试分与内部掌握概率配对，出相关报告。

配对口径：一场已录成绩(score_pct)且有学科(subject)的考试 → 该用户该学科所有 KP 的
平均 p_mastery（×100 转百分比）。跨多场考试算 Pearson 相关（理论地基 M10：验证不自欺）。
数据稀疏 → anchor_report 安全 no-op（correlation=None）。
"""
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.models.knowledge_point import KnowledgePoint
from app.eval import score_anchor


async def compute_score_anchor(db: AsyncSession, user_id: str | None = None) -> dict:
    """user_id 给定 → 仅该用户；None → 全局（运维/eval 验证度量）。"""
    # 1) 已录成绩 + 有学科的考试
    exam_q = select(Exam.user_id, Exam.subject, Exam.score_pct).where(
        Exam.score_pct.is_not(None), Exam.subject.is_not(None)
    )
    if user_id is not None:
        exam_q = exam_q.where(Exam.user_id == uuid.UUID(user_id))
    exams = (await db.execute(exam_q)).all()
    if not exams:
        return score_anchor.anchor_report([])

    # 2) 每个 (user, subject) 的平均内部掌握度
    mastery_q = (
        select(
            KnowledgePoint.user_id,
            KnowledgePoint.subject,
            func.avg(KnowledgePoint.p_mastery).label("avg_m"),
        )
        .where(KnowledgePoint.p_mastery.is_not(None), KnowledgePoint.subject.is_not(None))
        .group_by(KnowledgePoint.user_id, KnowledgePoint.subject)
    )
    if user_id is not None:
        mastery_q = mastery_q.where(KnowledgePoint.user_id == uuid.UUID(user_id))
    mastery = {
        (str(uid), subj): float(avg_m)
        for uid, subj, avg_m in (await db.execute(mastery_q)).all()
        if avg_m is not None
    }

    # 3) 配对（仅当该学科有掌握度数据）
    pairs: list[tuple[float, float]] = []
    for uid, subj, score in exams:
        avg_m = mastery.get((str(uid), subj))
        if avg_m is not None:
            pairs.append((float(score), avg_m * 100.0))

    return score_anchor.anchor_report(pairs)
