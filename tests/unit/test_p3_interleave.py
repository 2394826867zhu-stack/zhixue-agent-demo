# tests/unit/test_p3_interleave.py
"""学习内核 P3 · 交错出题（G-P3-3，[M5]）单元测试。

- confusable_neighbors：图谱近邻易混节点（共享直接先修的兄弟）。
- interleave：把按 KP 成块的题序列交错成 round-robin，避免同 KP 连续。
交错对象来自近邻边（验收：易混群内交错而非 blocked practice）。
"""
from app.services.graph_service import confusable_neighbors, interleave


# ── 易混近邻（共享先修的兄弟）──

def _edges():
    # P 是 A/B/C 的共同先修；Q 是 D 的先修
    return [("P", "A"), ("P", "B"), ("P", "C"), ("Q", "D")]


def test_confusable_siblings_share_prereq():
    assert confusable_neighbors("A", _edges()) == ["B", "C"]
    assert confusable_neighbors("B", _edges()) == ["A", "C"]


def test_confusable_excludes_non_sibling():
    """D 的先修是 Q，与 A/B/C 不共享先修 → 不互为易混。"""
    assert confusable_neighbors("D", _edges()) == []
    assert "D" not in confusable_neighbors("A", _edges())


def test_confusable_no_prereq_returns_empty():
    assert confusable_neighbors("P", _edges()) == []
    assert confusable_neighbors("Z", _edges()) == []


# ── 交错排列 ──

def test_interleave_two_groups():
    """[A,A,B,B] → [A,B,A,B]：易混两组交错，同 KP 不连续。"""
    assert interleave(["A", "A", "B", "B"]) == ["A", "B", "A", "B"]


def test_interleave_uneven_groups():
    """题数不均时尽力交错，多余的同 KP 落到末尾。"""
    assert interleave(["A", "A", "A", "B"]) == ["A", "B", "A", "A"]


def test_interleave_preserves_first_seen_order():
    assert interleave(["A", "B", "C"]) == ["A", "B", "C"]


def test_interleave_single_and_empty():
    assert interleave(["A", "A", "A"]) == ["A", "A", "A"]
    assert interleave(["A"]) == ["A"]
    assert interleave([]) == []


def test_interleave_total_preserved():
    """交错只重排不增删：各 KP 题数守恒。"""
    src = ["A", "A", "B", "C", "C", "C"]
    out = interleave(src)
    assert sorted(out) == sorted(src)
