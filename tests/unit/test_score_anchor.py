"""G-P4-2 · 外部成绩锚 — 纯函数单测（TDD 先行）。

把"内部掌握概率"与"真实考试分"做相关，验证度量不自欺（理论地基 M10 外部锚）。
空样本 / n<2 / 零方差 → correlation=None 安全 no-op。
"""
import pytest

from app.eval import score_anchor as sa


def test_empty_is_safe_noop():
    rep = sa.anchor_report([])
    assert rep["n"] == 0
    assert rep["correlation"] is None
    assert rep["mean_score_pct"] is None
    assert rep["mean_mastery_pct"] is None


def test_single_point_correlation_none():
    rep = sa.anchor_report([(80.0, 0.7)])
    assert rep["n"] == 1
    assert rep["correlation"] is None  # n<2 无相关可言
    assert rep["mean_score_pct"] == pytest.approx(80.0)
    assert rep["mean_mastery_pct"] == pytest.approx(0.7)


def test_strong_positive_correlation():
    # 掌握度越高考分越高 → 强正相关
    pairs = [(50.0, 0.4), (60.0, 0.5), (75.0, 0.65), (88.0, 0.8), (95.0, 0.92)]
    rep = sa.anchor_report(pairs)
    assert rep["n"] == 5
    assert rep["correlation"] is not None
    assert rep["correlation"] > 0.95


def test_negative_correlation():
    pairs = [(90.0, 0.2), (70.0, 0.5), (40.0, 0.9)]
    rep = sa.anchor_report(pairs)
    assert rep["correlation"] is not None
    assert rep["correlation"] < 0


def test_zero_variance_correlation_none():
    # 掌握度全相同 → 零方差 → None
    pairs = [(50.0, 0.6), (80.0, 0.6), (95.0, 0.6)]
    assert sa.anchor_report(pairs)["correlation"] is None


def test_means_computed():
    rep = sa.anchor_report([(60.0, 0.5), (80.0, 0.7)])
    assert rep["mean_score_pct"] == pytest.approx(70.0)
    assert rep["mean_mastery_pct"] == pytest.approx(0.6)
