"""阶段 B：检索评测 runner —— 跑标注集 → 算指标 → 聚合报告。"""
import pytest

from app.eval.retrieval_eval import evaluate_retrieval


@pytest.mark.asyncio
async def test_evaluate_retrieval_aggregates_metrics():
    cases = [
        {"id": "q1", "query": "导数", "relevant": ["a", "b"]},
        {"id": "q2", "query": "积分", "relevant": ["c"]},
    ]
    fixtures = {"导数": ["a", "b", "x"], "积分": ["y", "c"]}

    async def fake_search(query):
        return fixtures[query]

    report = await evaluate_retrieval(cases, fake_search, ks=(2,))

    assert report["n"] == 2
    # q1 recall@2 = 2/2=1, q2 recall@2 = 1/1=1 → mean 1.0
    assert report["mean_recall@2"] == 1.0
    # q1 mrr=1（a@1），q2 mrr=0.5（c@2）→ mean 0.75
    assert report["mean_mrr"] == 0.75
    assert len(report["per_case"]) == 2


@pytest.mark.asyncio
async def test_evaluate_retrieval_empty_cases():
    async def fake_search(query):
        return []

    report = await evaluate_retrieval([], fake_search, ks=(1,))
    assert report["n"] == 0
