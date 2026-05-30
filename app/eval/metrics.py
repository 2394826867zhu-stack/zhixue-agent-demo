"""检索评估指标（阶段 B 度量底座）。

retrieved：检索返回的 doc_id 列表（按相关性降序）
relevant：标注的应召回 doc_id 集合（二元相关性）
"""
import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """前 k 个结果命中的相关文档占全部相关文档的比例。"""
    if not relevant:
        return 0.0
    topk = set(retrieved[:k])
    return len(topk & relevant) / len(relevant)


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    """第一个命中相关文档的排名倒数；无命中为 0。"""
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """二元相关性 nDCG@k。"""
    if not relevant:
        return 0.0
    dcg = 0.0
    for rank, doc in enumerate(retrieved[:k], start=1):
        if doc in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0
