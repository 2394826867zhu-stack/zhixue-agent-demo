"""measurement_service — P0 测量优先的纯函数层。

本模块只放纯函数（无 DB、无 IO），便于单元测试与复用：
- retrievability / effective_mastery：FSRS 幂律遗忘层（G-P0-3）。

注：BKT（p_mastery 估计，G-P0-2）原计划也落在本模块，但在执行 G-P0-3 时
该部分尚未提交（见交付报告）。本文件先承载遗忘层，BKT 后续可直接追加。
"""

from datetime import datetime, timezone

# FSRS-4.5 幂律遗忘曲线：R(t,S) = (1 + FACTOR·t/S)^DECAY，t=S 时 R=0.9。
_FSRS_DECAY = -0.5
_FSRS_FACTOR = 19.0 / 81.0


def retrievability(
    *,
    stability: float,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """FSRS 幂律遗忘曲线，返回当前回忆概率 R∈(0,1]。

    last_reviewed_at=None 或 stability<=0 → R=1（按未衰减处理，兜底）。
    """
    if last_reviewed_at is None or stability <= 0:
        return 1.0
    now = now or datetime.now(timezone.utc)
    elapsed_days = max(0.0, (now - last_reviewed_at).total_seconds() / 86400.0)
    r = (1.0 + _FSRS_FACTOR * elapsed_days / stability) ** _FSRS_DECAY
    return max(0.0, min(1.0, r))


def effective_mastery(
    *,
    p_mastery: float | None,
    stability: float,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """有效掌握度 = 学没学会 × 还记不记得 = p_mastery × R。p_mastery=None → 0。"""
    if p_mastery is None:
        return 0.0
    try:
        r = retrievability(stability=stability, last_reviewed_at=last_reviewed_at, now=now)
    except Exception:
        r = 1.0
    return max(0.0, min(1.0, p_mastery * r))
