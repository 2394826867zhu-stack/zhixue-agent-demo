"""学习内核 P3 · 增益函数（gain_policy，G-P3-1）。

设计§3.3「上限形态：增益期望最大化」——把 P2 的固定优先级，进化成
可校准的单位时间增益打分，对候选动作排序，逼近"每一分钟都在 argmax"。

    gain ≈ E[Δp_mastery] × 遗忘风险(1−R) × 先修杠杆(下游数) × ZPD匹配 ÷ 预计耗时

全纯函数（零 DB / 零 IO），复用 measurement_service(BKT+FSRS) 与 graph_service，
便于 TDD、便于 G-P3-5 与 PFA/Best-LR 同数据对照。

兜底（设计§3.3 末 + §1.3）：增益未经真实数据校准前，本模块**不接管** P2 的
确定性优先级（recommend_actions 不变）；由 feature flag `LEARNING_GAIN_ENABLED`
（默认 False）控制是否启用增益排序。任一因子缺数据 → 取中性默认，绝不抛。
理论出处：M10(度量供给 Δp 期望 + 校准) / M7(ZPD) / M8(先修杠杆) / M3(遗忘)。
"""
from __future__ import annotations

import logging
import math
from datetime import datetime

from app.services.measurement_service import (
    bkt_update,
    retrievability,
    _BKT_P_SLIP,
    _BKT_P_GUESS,
)

logger = logging.getLogger(__name__)

# ZPD：最近发展区中心答对率（设计§3.2/§3.3，难度调到答对率≈0.85）
_ZPD_CENTER = 0.85
_ZPD_SPAN = 0.85          # 偏离中心的线性衰减跨度
_FORGET_FLOOR = 0.05      # 遗忘权重下限，避免乘法把整条 gain 抹平
_DEFAULT_MINUTES = 10.0   # 缺省单次动作耗时估计（分钟）


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _p_correct(p_mastery: float, *, slip: float = _BKT_P_SLIP, guess: float = _BKT_P_GUESS) -> float:
    """当前掌握度下的预期答对率：P(correct) = p·(1−slip) + (1−p)·guess。"""
    p = _clamp01(p_mastery)
    return p * (1 - slip) + (1 - p) * guess


# ── 因子 1：E[Δp_mastery]（BKT 期望增益）────────────────────────────────────

def expected_mastery_delta(p_mastery: float | None) -> float:
    """一次作答后掌握度的期望提升 = Σ P(结果)·(后验 − 先验)。

    E[Δp] = P(对)·(bkt(p,对) − p) + P(错)·(bkt(p,错) − p)
    天然边际递减：p 越接近 1 增益越小（没什么可学），驱动 argmax 偏向有空间的点。
    """
    if p_mastery is None:
        p_mastery = 0.0
    p = _clamp01(p_mastery)
    pc = _p_correct(p)
    after_correct = bkt_update(p, True)
    after_wrong = bkt_update(p, False)
    exp_post = pc * after_correct + (1 - pc) * after_wrong
    return max(0.0, exp_post - p)


# ── 因子 2：遗忘风险 (1−R) ────────────────────────────────────────────────

def forgetting_weight(
    *,
    stability: float | None,
    last_reviewed_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """遗忘风险权重 ∈ [floor, 1]。

    - 新点 / 无 FSRS 态（stability/last_reviewed_at 缺）→ 1.0：还没记住 = 最需要学，
      不能因 R=1 被遗忘项归零（设计§3.3 公式对"复习"语义，新点需满权重兜底）。
    - 已学点 → 1−R：记得越牢（R 高）越不急复习；R 随时间衰减 → 权重升。
    - floor 防绝对 0。
    """
    if stability is None or last_reviewed_at is None:
        return 1.0
    r = retrievability(stability=stability, last_reviewed_at=last_reviewed_at, now=now)
    return max(_FORGET_FLOOR, 1.0 - r)


# ── 因子 3：先修杠杆（下游节点数）──────────────────────────────────────────

def leverage(downstream_count: int) -> float:
    """先修杠杆 = 1 + log1p(下游可达节点数)。

    下游越多（越是地基）杠杆越大；log 缩放避免 hub 节点线性碾压；叶子(0)→1 不归零。
    下游数由 graph_service._reachable(node, 后继邻接) 在接入层计算后传入。
    """
    try:
        n = max(0, int(downstream_count))
    except (TypeError, ValueError):
        n = 0
    return 1.0 + math.log1p(n)


# ── 因子 4：ZPD 匹配 ──────────────────────────────────────────────────────

def zpd_match(correct_rate: float | None) -> float | None:
    """最近发展区匹配度 ∈ [0,1]，答对率越接近 _ZPD_CENTER(0.85) 越高。

    correct_rate=None → 返回 None（调用方用 BKT 估计答对率兜底）。
    """
    if correct_rate is None:
        return None
    return max(0.0, 1.0 - abs(_clamp01(correct_rate) - _ZPD_CENTER) / _ZPD_SPAN)


# ── 综合增益 ──────────────────────────────────────────────────────────────

def gain(candidate: dict) -> float:
    """候选动作的单位时间增益分（设计§3.3）。

    candidate 契约（缺字段取中性默认，绝不抛）：
      p_mastery: float            当前掌握概率
      stability: float | None     FSRS 稳定性（新点 None）
      last_reviewed_at: datetime | None
      downstream_count: int       先修杠杆 = 下游可达节点数
      recent_correct_rate: float | None  ZPD 用；缺则用 BKT 估计答对率
      est_minutes: float          预计耗时（分钟）
    """
    try:
        p = candidate.get("p_mastery")
        p = 0.0 if p is None else _clamp01(p)

        delta = expected_mastery_delta(p)
        fw = forgetting_weight(
            stability=candidate.get("stability"),
            last_reviewed_at=candidate.get("last_reviewed_at"),
        )
        lev = leverage(candidate.get("downstream_count", 0))

        z = zpd_match(candidate.get("recent_correct_rate"))
        if z is None:
            z = zpd_match(_p_correct(p)) or 0.0

        minutes = candidate.get("est_minutes") or _DEFAULT_MINUTES
        minutes = max(1.0, float(minutes))

        return max(0.0, delta * fw * lev * z / minutes)
    except Exception:  # noqa: BLE001 — 打分绝不拖垮调度主流程
        logger.exception("gain scoring failed for candidate=%s", candidate)
        return 0.0


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """按 gain 降序返回候选副本（每项附 `gain` 分）；不改原始输入。"""
    scored = [{**c, "gain": gain(c)} for c in candidates]
    scored.sort(key=lambda c: c["gain"], reverse=True)
    return scored
