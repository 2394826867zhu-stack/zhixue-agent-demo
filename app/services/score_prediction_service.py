"""
预测分数服务。
基于知识点掌握度 + 训练历史均分，估算各科目成绩区间。
数据不足时返回 None（不预测）。结果由 Agent 在对话中自然说出，不直接展示给用户。
"""
import uuid
import logging
from statistics import mean
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.knowledge_point import KnowledgePoint
from app.models.training import TrainingSession

logger = logging.getLogger(__name__)

_MASTERY_WEIGHT = {
    "new":       0.10,
    "learning":  0.45,
    "reviewing": 0.72,
    "mastered":  0.92,
}

_SUBJECT_TOTAL = {
    "数学": 150, "语文": 150, "英语": 150,
    "物理": 110, "化学": 100, "生物": 90,
    "历史": 100, "地理": 100, "政治": 100,
}
_MIN_KP_COUNT = 5


def _build_result(subject: str, kps: list, training_pct: float | None) -> dict:
    mastery_scores = [_MASTERY_WEIGHT.get(kp.mastery_status, 0.3) for kp in kps]
    mastery_avg = mean(mastery_scores)
    effective_training = training_pct if training_pct is not None else mastery_avg
    composite = mastery_avg * 0.6 + effective_training * 0.4
    total = _SUBJECT_TOTAL.get(subject, 150)
    center = round(composite * total)
    low = round(center * 0.93)
    high = round(center * 1.07)
    weak = [kp.name for kp in kps if kp.mastery_status in ("learning", "new")][:3]
    return {
        "subject": subject,
        "center": center,
        "range": (low, high),
        "weak_topics": weak,
        "kp_count": len(kps),
    }


async def predict(db: AsyncSession, user_id: str, subject: str) -> dict | None:
    """
    预测单科成绩。返回 {"subject", "center", "range": (min, max), "weak_topics"} 或 None。
    """
    uid = uuid.UUID(user_id)

    kp_rows = await db.execute(
        select(KnowledgePoint.mastery_status, KnowledgePoint.name)
        .where(KnowledgePoint.user_id == uid, KnowledgePoint.subject == subject)
    )
    kps = kp_rows.all()
    if len(kps) < _MIN_KP_COUNT:
        return None

    train_row = await db.execute(
        select(func.avg(TrainingSession.avg_score))
        .where(
            TrainingSession.user_id == uid,
            TrainingSession.subject == subject,
            TrainingSession.status == "completed",
        )
    )
    train_avg_raw = train_row.scalar_one_or_none()
    training_pct = float(train_avg_raw) / 100 if train_avg_raw else None

    return _build_result(subject, kps, training_pct)


async def predict_all(db: AsyncSession, user_id: str) -> list[dict]:
    """
    预测用户所有有数据的科目。
    两次查询代替逐科 2N+1 次：一次拉全部 KP，一次拉全部训练均分。
    """
    uid = uuid.UUID(user_id)

    # 1. 全部 KP（mastery_status + name + subject）
    kp_rows = await db.execute(
        select(KnowledgePoint.mastery_status, KnowledgePoint.name, KnowledgePoint.subject)
        .where(KnowledgePoint.user_id == uid, KnowledgePoint.subject.isnot(None))
    )
    # group by subject in Python
    subject_kps: dict[str, list] = {}
    for row in kp_rows.all():
        subject_kps.setdefault(row.subject, []).append(row)

    qualifying = [s for s, kps in subject_kps.items() if len(kps) >= _MIN_KP_COUNT]
    if not qualifying:
        return []

    # 2. 训练均分（只查有数据的科目）
    train_rows = await db.execute(
        select(TrainingSession.subject, func.avg(TrainingSession.avg_score))
        .where(
            TrainingSession.user_id == uid,
            TrainingSession.subject.in_(qualifying),
            TrainingSession.status == "completed",
        )
        .group_by(TrainingSession.subject)
    )
    training_avgs: dict[str, float] = {}
    for subj, avg in train_rows.all():
        if avg is not None:
            training_avgs[subj] = float(avg) / 100

    results = []
    for subject in qualifying:
        kps = subject_kps[subject]
        training_pct = training_avgs.get(subject)
        results.append(_build_result(subject, kps, training_pct))

    return results
