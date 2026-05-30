"""C-12 引用展示后端契约：RAG 召回 → 前端可展示的引用来源结构。"""
from app.services.rag_service import format_citations


def test_format_citations_labels_each_source_kind():
    hits = [
        {"doc_kind": "mistake", "doc_id": "m1", "content": "题目：求2x导数", "score": 0.913, "metadata": {}},
        {"doc_kind": "note", "doc_id": "n1", "content": "导数的定义……", "score": 0.85, "metadata": {"title": "导数笔记"}},
        {"doc_kind": "kp", "doc_id": "k1", "content": "导数", "score": 0.8, "metadata": {"title": "导数知识点"}},
    ]
    cites = format_citations(hits)
    assert cites[0]["source_label"] == "错题"
    assert cites[1]["source_label"] == "笔记"
    assert cites[2]["source_label"] == "知识点"


def test_format_citations_uses_title_else_content_snippet():
    hits = [
        {"doc_kind": "note", "doc_id": "n1", "content": "x" * 100, "score": 0.9, "metadata": {"title": "我的笔记"}},
        {"doc_kind": "mistake", "doc_id": "m1", "content": "y" * 100, "score": 0.7, "metadata": {}},
    ]
    cites = format_citations(hits)
    assert cites[0]["title"] == "我的笔记"
    # 无 title 时退化为内容截断
    assert cites[1]["title"] == "y" * 30
    assert cites[0]["doc_id"] == "n1"
    assert cites[0]["score"] == 0.9


def test_format_citations_empty():
    assert format_citations([]) == []
