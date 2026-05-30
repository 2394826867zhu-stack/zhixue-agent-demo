"""检索评测 runner（阶段 B 度量底座）。

给定标注评估集（每条含 query + relevant doc_id 列表）+ 一个 async 检索函数
（query -> list[doc_id]），跑出逐条与聚合的 Recall@K / MRR / nDCG@K 报告。
这是阶段 C 检索升级（BM25/混合/rerank）做 A/B 对比的基线工具。
"""
from collections.abc import Awaitable, Callable

from app.eval.metrics import recall_at_k, mrr, ndcg_at_k

SearchFn = Callable[[str], Awaitable[list[str]]]


def make_rag_search_fn(
    db,
    user_id,
    org_id=None,
    top_k: int = 10,
    doc_kinds: list[str] | None = None,
) -> SearchFn:
    """把 rag_service.search 包装成 runner 需要的 search_fn（query -> doc_id 列表）。"""
    from app.services import rag_service

    async def _fn(query: str) -> list[str]:
        hits = await rag_service.search(
            db,
            user_id=user_id,
            query=query,
            org_id=org_id,
            top_k=top_k,
            doc_kinds=doc_kinds,
        )
        return [h["doc_id"] for h in hits]

    return _fn


async def evaluate_retrieval(
    cases: list[dict],
    search_fn: SearchFn,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    per_case = []
    for c in cases:
        retrieved = await search_fn(c["query"])
        relevant = set(c["relevant"])
        row = {"id": c.get("id"), "mrr": mrr(retrieved, relevant)}
        for k in ks:
            row[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
            row[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
        per_case.append(row)

    report: dict = {"n": len(per_case), "per_case": per_case}
    if per_case:
        report["mean_mrr"] = sum(r["mrr"] for r in per_case) / len(per_case)
        for k in ks:
            report[f"mean_recall@{k}"] = sum(
                r[f"recall@{k}"] for r in per_case
            ) / len(per_case)
            report[f"mean_ndcg@{k}"] = sum(
                r[f"ndcg@{k}"] for r in per_case
            ) / len(per_case)
    return report
