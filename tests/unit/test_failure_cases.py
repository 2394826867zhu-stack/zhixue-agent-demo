"""G-P4-3 · 失败案例沉淀回 eval 集 — 纯函数单测（TDD 先行）。

沿用 RAG 阶段做法（build → merge 沉淀，随真实数据增长）：
把探针失败 / 低分作答沉淀成学习内核回归 eval 集，"惊讶失败"（高掌握却答错=模型高估）最有信息量。
"""
import pytest

from app.eval import failure_cases as fc


def _rec(kp, correct, kind="practice", subject="math", reason=None, mastery=0.5):
    return {"kp_id": kp, "subject": subject, "kind": kind, "correct": correct,
            "error_reason": reason, "p_mastery": mastery}


def test_build_filters_failures_only():
    recs = [_rec("k1", False), _rec("k2", True), _rec("k1", False)]
    s = fc.build_failure_set(recs)
    keys = {c["kp_id"] for c in s["cases"]}
    assert keys == {"k1"}                       # 只留失败
    assert s["total_records"] == 3


def test_build_dedups_and_counts():
    recs = [_rec("k1", False, reason="concept"), _rec("k1", False, reason="careless"),
            _rec("k1", False, reason="concept")]
    s = fc.build_failure_set(recs)
    assert len(s["cases"]) == 1
    c = s["cases"][0]
    assert c["wrong_count"] == 3
    assert c["error_reasons"]["concept"] == 2
    assert c["error_reasons"]["careless"] == 1


def test_surprising_when_high_mastery_yet_fail():
    # 掌握度高(>=0.6)却答错 = 模型高估，标 surprising
    s = fc.build_failure_set([_rec("k1", False, mastery=0.85)])
    assert s["cases"][0]["surprising"] is True
    s2 = fc.build_failure_set([_rec("k2", False, mastery=0.3)])
    assert s2["cases"][0]["surprising"] is False


def test_merge_grows_and_accumulates():
    s1 = fc.build_failure_set([_rec("k1", False, reason="concept")])
    s2 = fc.build_failure_set([_rec("k1", False, reason="method"), _rec("k2", False)])
    merged = fc.merge_failure_sets(s1, s2)
    by = {c["kp_id"]: c for c in merged["cases"]}
    assert set(by) == {"k1", "k2"}              # 新 key 进集
    assert by["k1"]["wrong_count"] == 2          # 频次累加（随数据增长）
    assert by["k1"]["error_reasons"] == {"concept": 1, "method": 1}


def test_merge_surprising_is_or():
    s1 = fc.build_failure_set([_rec("k1", False, mastery=0.3)])
    s2 = fc.build_failure_set([_rec("k1", False, mastery=0.9)])
    merged = fc.merge_failure_sets(s1, s2)
    assert merged["cases"][0]["surprising"] is True


def test_empty_safe():
    assert fc.build_failure_set([])["cases"] == []
    assert fc.merge_failure_sets()["cases"] == []
    stats = fc.failure_set_stats(fc.build_failure_set([]))
    assert stats["n_cases"] == 0 and stats["total_wrong"] == 0


def test_stats():
    s = fc.build_failure_set([_rec("k1", False, mastery=0.9), _rec("k1", False, mastery=0.9),
                              _rec("k2", False, mastery=0.2)])
    st = fc.failure_set_stats(s)
    assert st["n_cases"] == 2
    assert st["total_wrong"] == 3
    assert st["surprising_count"] == 1
