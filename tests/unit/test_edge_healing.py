"""G-P1-6 · 数据驱动图谱边自愈 — 纯函数单测（TDD 先行）。

先修边 A→B 的数据校验：学生明确掌握了下游 B 却没掌握先修 A → 该边被违例（A 可能不是真先修）。
违例 → confidence 衰减；持续违例衰减到地板 → 剪除（自愈，非人工边）；一致 → 轻微加固。
"""
import pytest

from app.services import edge_healing as eh


def test_edge_health_violated():
    # 下游明确掌握(>=0.8) 先修明确未掌握(<=0.4) → 违例
    assert eh.edge_health(from_mastery=0.2, to_mastery=0.9) == "violated"


def test_edge_health_consistent():
    assert eh.edge_health(from_mastery=0.7, to_mastery=0.75) == "consistent"


def test_edge_health_unobserved():
    # 下游还没掌握 → 无信号
    assert eh.edge_health(from_mastery=0.2, to_mastery=0.3) == "unobserved"


def test_heal_confidence_decay_and_reinforce():
    assert eh.heal_confidence(0.8, "violated") < 0.8
    assert eh.heal_confidence(0.8, "consistent") >= 0.8
    assert eh.heal_confidence(0.8, "unobserved") == 0.8


def test_heal_confidence_reinforce_capped():
    assert eh.heal_confidence(0.99, "consistent") <= 1.0


def test_repeated_violation_decays_to_floor():
    c = 0.9
    for _ in range(20):
        c = eh.heal_confidence(c, "violated")
    assert c < eh._FLOOR  # 持续违例 → 跌破地板（触发剪除）
