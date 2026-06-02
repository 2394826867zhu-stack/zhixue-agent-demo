# tests/unit/test_gain_policy.py
"""学习内核 P3 · 增益函数 gain_policy（G-P3-1）单元测试。

设计§3.3:
  gain ≈ E[Δp_mastery] × 遗忘风险(1−R) × 先修杠杆(下游数) × ZPD匹配 ÷ 耗时
全纯函数，复用 measurement(BKT+FSRS) + graph。零 DB / 零 IO。
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services.gain_policy import (
    expected_mastery_delta,
    forgetting_weight,
    leverage,
    zpd_match,
    gain,
    rank_candidates,
    _DEFAULT_MINUTES,
)


# ── E[Δp_mastery]：BKT 期望增益 ──

def test_delta_nonnegative():
    """学习的期望掌握增益恒非负。"""
    for p in (0.0, 0.1, 0.3, 0.5, 0.9, 1.0):
        assert expected_mastery_delta(p) >= 0.0


def test_delta_diminishing_returns():
    """低掌握度的期望增益 > 高掌握度（边际递减 → argmax 偏向有提升空间的点）。"""
    assert expected_mastery_delta(0.2) > expected_mastery_delta(0.85)


def test_delta_near_mastered_is_small():
    """已近满掌握 → 期望增益趋近 0（没什么可学了）。"""
    assert expected_mastery_delta(0.99) < 0.05


def test_delta_handles_none():
    """p_mastery=None 当作 0 处理，不崩。"""
    assert expected_mastery_delta(None) >= 0.0


# ── 遗忘风险因子 (1−R) ──

def test_forgetting_new_point_full_weight():
    """新点（无 FSRS 态）→ 满权重 1.0，不被遗忘项归零（最需要学）。"""
    assert forgetting_weight(stability=None, last_reviewed_at=None) == pytest.approx(1.0)


def test_forgetting_just_reviewed_low_weight():
    """刚复习完（R≈1）→ 权重接近下限（不急着再复习）。"""
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    w = forgetting_weight(stability=10.0, last_reviewed_at=now, now=now)
    assert w < 0.2


def test_forgetting_long_ago_higher_weight():
    """久未复习 R 衰减 → 权重高于刚复习。"""
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    fresh = forgetting_weight(stability=10.0, last_reviewed_at=now, now=now)
    stale = forgetting_weight(stability=10.0, last_reviewed_at=now - timedelta(days=60), now=now)
    assert stale > fresh


def test_forgetting_never_absolute_zero():
    """floor 保证永不绝对 0，避免乘法把整条 gain 抹平。"""
    now = datetime(2026, 6, 2, tzinfo=timezone.utc)
    assert forgetting_weight(stability=999.0, last_reviewed_at=now, now=now) > 0.0


# ── 先修杠杆 ──

def test_leverage_monotonic():
    """下游节点越多，杠杆越大（地基知识点更值得先学）。"""
    assert leverage(0) < leverage(3) < leverage(20)


def test_leverage_leaf_nonzero():
    """叶子节点（下游 0）杠杆 ≥ 1，不把 gain 归零。"""
    assert leverage(0) >= 1.0


def test_leverage_log_scaled():
    """log 缩放：hub 节点不线性碾压（100 倍下游不等于 100 倍杠杆）。"""
    assert leverage(100) < 100 * leverage(1)


# ── ZPD 匹配 ──

def test_zpd_peak_at_center():
    """答对率 = 0.85（ZPD 中心）→ 匹配度最高。"""
    assert zpd_match(0.85) > zpd_match(0.5)
    assert zpd_match(0.85) > zpd_match(1.0)


def test_zpd_too_easy_or_hard_low():
    """太简单(1.0 全对)或太难(0.2)→ 匹配度低。"""
    assert zpd_match(1.0) < zpd_match(0.85)
    assert zpd_match(0.2) < zpd_match(0.85)


def test_zpd_none_returns_none():
    """无答对率数据 → None（调用方用估计答对率兜底）。"""
    assert zpd_match(None) is None


# ── 综合 gain ──

def _cand(**kw):
    base = {
        "kp_id": "k", "name": "x", "p_mastery": 0.3,
        "stability": None, "last_reviewed_at": None,
        "downstream_count": 0, "recent_correct_rate": None,
        "est_minutes": _DEFAULT_MINUTES,
    }
    base.update(kw)
    return base


def test_gain_nonnegative():
    assert gain(_cand()) >= 0.0


def test_gain_leverage_raises_score():
    """其他相同，下游多的候选 gain 更高。"""
    assert gain(_cand(downstream_count=10)) > gain(_cand(downstream_count=0))


def test_gain_shorter_time_higher():
    """耗时短 → 单位时间增益更高。"""
    assert gain(_cand(est_minutes=5)) > gain(_cand(est_minutes=30))


def test_gain_new_point_not_zeroed():
    """新点（无 FSRS 态）gain > 0，不被遗忘项抹平。"""
    assert gain(_cand(p_mastery=0.1, stability=None, last_reviewed_at=None)) > 0.0


def test_gain_zpd_uses_estimated_rate_when_missing():
    """缺答对率时用 BKT 估计答对率算 ZPD，仍给出有限正分。"""
    g = gain(_cand(recent_correct_rate=None))
    assert g > 0.0


def test_gain_failsafe_on_garbage():
    """字段缺失/类型异常 → 返回 0，不抛（绝不拖垮主流程）。"""
    assert gain({}) >= 0.0
    assert gain({"p_mastery": "bad"}) >= 0.0


# ── 排序 ──

def test_rank_descending_by_gain():
    cands = [
        _cand(kp_id="low", downstream_count=0, est_minutes=30),
        _cand(kp_id="high", downstream_count=20, est_minutes=5),
    ]
    ranked = rank_candidates(cands)
    assert ranked[0]["kp_id"] == "high"
    assert ranked[0]["gain"] >= ranked[1]["gain"]
    assert all("gain" in c for c in ranked)


def test_rank_empty():
    assert rank_candidates([]) == []


def test_rank_does_not_mutate_input():
    cands = [_cand(kp_id="a")]
    rank_candidates(cands)
    assert "gain" not in cands[0]  # 原始候选不被污染
