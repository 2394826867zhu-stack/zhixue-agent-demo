"""F 召回侧：出题前召回用户历史错题，注入出题 prompt（"基于你的错题出题"）。"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_recall_mistakes_hint_formats(monkeypatch):
    from app.services.training_service import training_service

    async def fake_search(db, **kw):
        assert kw.get("doc_kinds") == ["mistake"]
        return [{"content": "题目：2+2=? 我的错误答案：5 错误原因：concept", "doc_id": "x"}]

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    hint = await training_service._recall_mistakes_hint(None, str(uuid.uuid4()), "math")
    assert "易错" in hint
    assert "2+2" in hint


@pytest.mark.asyncio
async def test_recall_mistakes_hint_empty_when_no_mistakes(monkeypatch):
    from app.services.training_service import training_service

    async def fake_search(db, **kw):
        return []

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    hint = await training_service._recall_mistakes_hint(None, str(uuid.uuid4()), "math")
    assert hint == ""


@pytest.mark.asyncio
async def test_recall_mistakes_hint_degrades_on_error(monkeypatch):
    from app.services.training_service import training_service

    async def boom(db, **kw):
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.services.rag_service.search", boom)

    # 召回失败不可阻断出题
    hint = await training_service._recall_mistakes_hint(None, str(uuid.uuid4()), "math")
    assert hint == ""
