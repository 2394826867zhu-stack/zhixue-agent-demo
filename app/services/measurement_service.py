"""measurement_service — P0 测量优先的纯函数层。

本模块只放纯函数（无 DB、无 IO），便于单元测试与复用：
- retrievability / effective_mastery：FSRS 幂律遗忘层（G-P0-3）。

注：BKT（p_mastery 估计，G-P0-2）原计划也落在本模块，但在执行 G-P0-3 时
该部分尚未提交（见交付报告）。本文件先承载遗忘层，BKT 后续可直接追加。
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# FSRS-4.5 幂律遗忘曲线：R(t,S) = (1 + FACTOR·t/S)^DECAY，t=S 时 R=0.9。
_FSRS_DECAY = -0.5
_FSRS_FACTOR = 19.0 / 81.0

# BKT（贝叶斯知识追踪）参数
_BKT_P_TRANSIT = 0.15   # P(L)：一次练习从未掌握→掌握的转移概率
_BKT_P_SLIP = 0.10      # P(S)：已掌握却答错
_BKT_P_GUESS = 0.25     # P(G)：未掌握却答对（知曜取 0.25 而非文献常见 0.20：知曜题库含较多选择/判断题，四选一蒙对率≈0.25 更贴合实际；仍 ≤0.5 钳制线内。见 P0 审计 A-4）
_BKT_P_INIT = 0.30      # P(L0)：先验掌握度
P_INIT = _BKT_P_INIT    # 公开别名（先验掌握度，供调用方/测试引用）
_BKT_CLAMP = 0.5        # M2 防退化：guess/slip 硬钳制到 [0,0.5]


def _clamp_half(x: float) -> float:
    return max(0.0, min(_BKT_CLAMP, x))


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


def bkt_update(
    prior: float | None, correct: bool,
    *, p_transit: float = _BKT_P_TRANSIT, p_slip: float = _BKT_P_SLIP,
    p_guess: float = _BKT_P_GUESS, p_init: float = _BKT_P_INIT,
    slip: float | None = None, guess: float | None = None,
) -> float:
    """单步 BKT 更新：给定先验 P(L) 与一次作答对错，返回后验 P(L)。

    slip/guess 为 p_slip/p_guess 的别名（兼容写法）。两者运行时硬钳制到
    [0,0.5]（M2 防退化），避免 guess/slip 过大反转对错信号。
    """
    if slip is not None:
        p_slip = slip
    if guess is not None:
        p_guess = guess
    p_slip = _clamp_half(p_slip)
    p_guess = _clamp_half(p_guess)
    p = p_init if prior is None else prior
    p = min(1.0, max(0.0, p))
    if correct:
        num = p * (1 - p_slip)
        den = p * (1 - p_slip) + (1 - p) * p_guess
    else:
        num = p * p_slip
        den = p * p_slip + (1 - p) * (1 - p_guess)
    posterior_obs = num / den if den > 0 else p
    # 学习转移：观测后再过一次学习机会
    p_post = posterior_obs + (1 - posterior_obs) * p_transit
    return min(1.0, max(0.0, p_post))


def apply_answer_to_kp(kp, correct: bool) -> None:
    """把一次作答应用到 KP 的 p_mastery（就地更新，不 commit）。"""
    kp.p_mastery = bkt_update(getattr(kp, "p_mastery", None), correct)


async def update_mastery_on_answer(db, kp_id, correct: bool) -> None:
    """DB 包装：取 KP → apply_answer_to_kp（就地更新，不 flush 不 commit，事务边界交调用方）。

    kp_id=None 安全跳过；任何异常吞掉记日志，绝不拖垮答题主流程（fail-safe）。
    与 probe_service.record_probe_result 保持一致：均不自行 flush/commit（审计 A-6）。
    """
    if kp_id is None:
        return
    from app.models.knowledge_point import KnowledgePoint
    try:
        kp = await db.get(KnowledgePoint, kp_id)
        if kp is None:
            return
        apply_answer_to_kp(kp, correct=correct)
    except Exception:  # noqa: BLE001
        logger.exception("update_mastery_on_answer failed kp_id=%s", kp_id)
