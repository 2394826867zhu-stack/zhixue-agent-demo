"""G-P4-4 · 10 倍/效率仪表盘 — 纯函数单测（TDD 先行）。

诚实铁律（理论地基 M1）：产出按 +1σ 表述、"10 倍"仅用于效率维度、不喊未经证据的产出倍数。
空样本安全：无数据时增益=None，但诚实框架表述始终在场。
"""
import pytest

from app.eval import dashboard as db
from app.services.measurement_service import P_INIT


def _empty_anchor():
    return {"n": 0, "correlation": None, "mean_score_pct": None, "mean_mastery_pct": None}


def test_empty_safe_but_honesty_present():
    rep = db.efficiency_dashboard(
        avg_mastery_pct=None, probed_kp_count=0, focus_minutes=0, anchor=_empty_anchor()
    )
    # 增益无数据 → None
    assert rep["output_effect"]["normalized_gain"] is None
    assert rep["efficiency"]["mastery_gain_per_hour"] is None
    # 诚实框架始终在场（不依赖数据）
    assert "+1σ" in rep["output_effect"]["honest_ceiling"]
    assert "效率" in rep["efficiency"]["claim_scope"]
    assert rep["honesty_note"]
    # 不喊 10 倍产出：产出维度文案不得出现"10 倍"
    assert "10" not in rep["output_effect"]["honest_ceiling"]


def test_normalized_gain_hake_formula():
    # avg_mastery 70% ，基线 = P_INIT(30%) → ⟨g⟩ = (70-30)/(100-30)
    rep = db.efficiency_dashboard(
        avg_mastery_pct=70.0, probed_kp_count=10, focus_minutes=600, anchor=_empty_anchor()
    )
    expected = (70.0 - P_INIT * 100) / (100 - P_INIT * 100)
    assert rep["output_effect"]["normalized_gain"] == pytest.approx(expected, abs=1e-6)
    assert rep["output_effect"]["avg_mastery_pct"] == pytest.approx(70.0)
    assert rep["output_effect"]["probed_kp_count"] == 10


def test_mastery_gain_per_hour():
    # delta = 0.7 - 0.3 = 0.4 over 600min=10h → 0.04 /h
    rep = db.efficiency_dashboard(
        avg_mastery_pct=70.0, probed_kp_count=10, focus_minutes=600, anchor=_empty_anchor()
    )
    assert rep["efficiency"]["mastery_gain_per_hour"] == pytest.approx(0.04, abs=1e-6)
    assert rep["efficiency"]["focus_minutes"] == 600


def test_zero_focus_gain_per_hour_none():
    rep = db.efficiency_dashboard(
        avg_mastery_pct=70.0, probed_kp_count=10, focus_minutes=0, anchor=_empty_anchor()
    )
    assert rep["efficiency"]["mastery_gain_per_hour"] is None


def test_external_anchor_passed_through():
    anchor = {"n": 3, "correlation": 0.91, "mean_score_pct": 70.0, "mean_mastery_pct": 65.0}
    rep = db.efficiency_dashboard(
        avg_mastery_pct=65.0, probed_kp_count=5, focus_minutes=300, anchor=anchor
    )
    assert rep["external_anchor"]["correlation"] == pytest.approx(0.91)


def test_no_fabricated_efficiency_multiplier():
    # 效率维度不得给出具体倍数字段（须真实数据支撑，未达标不宣称）
    rep = db.efficiency_dashboard(
        avg_mastery_pct=80.0, probed_kp_count=20, focus_minutes=1200, anchor=_empty_anchor()
    )
    assert "efficiency_multiplier" not in rep["efficiency"]
    assert "10x" not in str(rep["efficiency"].get("mastery_gain_per_hour", ""))
