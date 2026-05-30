"""阶段 B 度量底座：检索评估指标 Recall@K / MRR / nDCG。"""
import pytest

from app.eval.metrics import recall_at_k, mrr, ndcg_at_k


# ---- Recall@K ----
def test_recall_at_k_partial():
    # [a,b] 命中 a；relevant={a,c} → 1/2
    assert recall_at_k(["a", "b", "c", "d"], {"a", "c"}, k=2) == 0.5


def test_recall_at_k_full():
    assert recall_at_k(["a", "b", "c", "d"], {"a", "c"}, k=4) == 1.0


def test_recall_at_k_none_hit():
    assert recall_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_recall_at_k_empty_relevant_is_zero():
    assert recall_at_k(["a"], set(), k=1) == 0.0


# ---- MRR ----
def test_mrr_rank1():
    assert mrr(["a", "b"], {"a"}) == 1.0


def test_mrr_rank2():
    assert mrr(["b", "a", "c"], {"a"}) == 0.5


def test_mrr_no_hit():
    assert mrr(["x", "y"], {"a"}) == 0.0


# ---- nDCG ----
def test_ndcg_perfect_order():
    # relevant 排在最前 → 1.0
    assert ndcg_at_k(["a", "b", "c"], {"a", "b"}, k=3) == pytest.approx(1.0)


def test_ndcg_suboptimal_between_0_and_1():
    val = ndcg_at_k(["c", "a", "b"], {"a", "b"}, k=3)
    assert 0.0 < val < 1.0


def test_ndcg_empty_relevant_is_zero():
    assert ndcg_at_k(["a"], set(), k=1) == 0.0
