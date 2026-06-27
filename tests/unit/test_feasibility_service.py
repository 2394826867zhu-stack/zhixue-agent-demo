"""INC-D 可行性估算 单测（纯逻辑，无 DB）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §5.4
"""
from datetime import datetime, timedelta, timezone

from app.services import feasibility_service as feas


def test_feasibility_bands_at_boundaries():
    # 档位边界 0.8 / 1.2 / 2.0（spec §5.4）
    assert feas.feasibility_band(0.5) == "ample"
    assert feas.feasibility_band(0.8) == "ample"
    assert feas.feasibility_band(0.81) == "fit"
    assert feas.feasibility_band(1.2) == "fit"
    assert feas.feasibility_band(1.21) == "tight"
    assert feas.feasibility_band(2.0) == "tight"
    assert feas.feasibility_band(2.01) == "infeasible"


def test_estimate_feasibility_ratio_and_band():
    # 估 80h，可用 100h → ratio 0.8 → ample
    r = feas.estimate_feasibility(estimated_hours=80, weekly_hours=10, remaining_weeks_val=10)
    assert r["ratio"] == 0.8 and r["band"] == "ample"
    assert r["available_hours"] == 100.0 and r["estimated_hours"] == 80.0
    # 估 300h，可用 100h → ratio 3.0 → infeasible
    r2 = feas.estimate_feasibility(estimated_hours=300, weekly_hours=10, remaining_weeks_val=10)
    assert r2["band"] == "infeasible" and r2["advice"]


def test_no_weekly_hours_is_unknown():
    r = feas.estimate_feasibility(estimated_hours=50, weekly_hours=None, remaining_weeks_val=8)
    assert r["band"] == "unknown" and r["ratio"] is None and r["advice"] == ""


def test_prompt_advice_varies_by_band():
    # fit/unknown → 不注入；ample/tight/infeasible → 有指令
    assert feas.feasibility_advice_for_prompt("fit") is None
    assert feas.feasibility_advice_for_prompt("unknown") is None
    assert "充裕" in feas.feasibility_advice_for_prompt("ample")
    assert "optional" in feas.feasibility_advice_for_prompt("tight")
    assert "optional" in feas.feasibility_advice_for_prompt("infeasible")


def test_estimate_node_count_clamped_and_sensible():
    # prerequisites_only 比 full_subject 少；都钳在 8-30
    full = feas.estimate_node_count("exam", "full_subject", "deep")
    prereq = feas.estimate_node_count("interest", "prerequisites_only", "surface")
    assert 8 <= prereq <= full <= 30


def test_hours_from_counts_by_difficulty():
    # 蓝0.5 紫1 金2：4蓝+4紫+2金 = 2+4+4 = 10h
    assert feas.estimate_hours_from_counts(4, 4, 2) == 10.0


def test_remaining_weeks():
    future = datetime.now(timezone.utc) + timedelta(weeks=6)
    assert 5.5 <= feas.remaining_weeks(future) <= 6.0
    # 无日期 → default
    assert feas.remaining_weeks(None, default=12) == 12.0
    # 过去日期 → 至少 1 周（不为负）
    past = datetime.now(timezone.utc) - timedelta(weeks=4)
    assert feas.remaining_weeks(past) == 1.0
