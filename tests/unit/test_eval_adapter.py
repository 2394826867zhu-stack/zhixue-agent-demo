"""阶段 B3：评测 runner 接真实 rag_service.search 的适配器。"""
import pytest

from app.eval import retrieval_eval


@pytest.mark.asyncio
async def test_make_rag_search_fn_extracts_doc_ids(monkeypatch):
    async def fake_search(db, *, user_id, query, **kw):
        return [
            {"doc_id": "d1", "score": 0.9},
            {"doc_id": "d2", "score": 0.8},
        ]

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    fn = retrieval_eval.make_rag_search_fn(db=None, user_id="u1", top_k=5)
    result = await fn("什么是导数")
    assert result == ["d1", "d2"]


@pytest.mark.asyncio
async def test_make_rag_search_fn_passes_org_and_kinds(monkeypatch):
    captured = {}

    async def fake_search(db, *, user_id, query, **kw):
        captured.update(kw)
        captured["user_id"] = user_id
        return []

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    fn = retrieval_eval.make_rag_search_fn(
        db=None, user_id="u1", org_id="org9", top_k=7, doc_kinds=["kp"]
    )
    await fn("q")
    assert captured["user_id"] == "u1"
    assert captured["org_id"] == "org9"
    assert captured["top_k"] == 7
    assert captured["doc_kinds"] == ["kp"]
