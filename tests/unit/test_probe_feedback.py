"""G-P4-1 · 探针结果回流策略 — 纯函数单测（TDD 先行）。

遗忘/迁移失败 → 调度调整（[M9][M10]）。policy 是纯函数，决定回流动作。
"""
import pytest

from app.services import probe_feedback as pf


def test_retention_fail_reschedules_sooner():
    d = pf.probe_feedback_policy("retention", correct=False)
    assert d["reschedule"] == "sooner"
    assert d["demote"] is False
    assert d["reason"]


def test_retention_pass_no_intervention():
    d = pf.probe_feedback_policy("retention", correct=True)
    assert d["reschedule"] in ("later", "none")
    assert d["demote"] is False


def test_transfer_fail_demotes_and_reschedules():
    d = pf.probe_feedback_policy("transfer", correct=False)
    # 迁移失败：背了没真懂 → 掌握度下调 + 重回练习
    assert d["demote"] is True
    assert d["reschedule"] == "sooner"
    assert d["reason"]


def test_transfer_pass_confirms():
    d = pf.probe_feedback_policy("transfer", correct=True)
    assert d["demote"] is False


def test_unknown_kind_safe():
    d = pf.probe_feedback_policy("weird", correct=False)
    assert d["reschedule"] == "none"
    assert d["demote"] is False
