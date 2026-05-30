"""E 可观测·第一步：RAG 召回质量指标（让"召回好不好"可量化）。

summarize_retrieval(query, hits) → 结构化指标，接结构化埋点日志，
数据驱动后续检索/上下文迭代。"""
from app.services.rag_service import summarize_retrieval


def test_summarizes_hit_count_and_score_distribution():
    hits = [
        {"doc_kind": "mistake", "score": 0.9, "doc_id": "m1"},
        {"doc_kind": "note", "score": 0.8, "doc_id": "n1"},
        {"doc_kind": "note", "score": 0.7, "doc_id": "n2"},
    ]
    s = summarize_retrieval("2x的导数", hits)
    assert s["hit_count"] == 3
    assert s["is_empty"] is False
    assert s["score_max"] == 0.9
    assert s["score_min"] == 0.7
    assert round(s["score_avg"], 4) == 0.8
    # doc_kind 命中分布
    assert s["kind_distribution"] == {"mistake": 1, "note": 2}


def test_empty_hits_flagged_for_zero_recall_tracking():
    s = summarize_retrieval("无关问题", [])
    assert s["hit_count"] == 0
    assert s["is_empty"] is True
    assert s["score_max"] is None
    assert s["score_min"] is None
    assert s["score_avg"] is None
    assert s["kind_distribution"] == {}


def test_includes_query_length_not_raw_query():
    # 不落原始 query（隐私）；只记长度供分析
    s = summarize_retrieval("一段较长的用户问题文本", [{"doc_kind": "kp", "score": 0.5, "doc_id": "k1"}])
    assert "query" not in s
    assert s["query_len"] == len("一段较长的用户问题文本")
