"""C-12 引用展示后端接入：Agent SSE `done` 事件携带 RAG 召回来源（sources）。

让前端能展示"答案参考了你的：错题《求2x导数》/ 笔记《导数》"。
"""
import json
import uuid

import pytest


class _FakeMsg:
    def __init__(self):
        self.content = "好的"
        self.tool_calls = None

    def model_dump(self):
        return {}


class _FakeChoice:
    """LLM 直接回答（无工具调用），让工具循环立即退出。"""

    def __init__(self):
        self.finish_reason = "stop"
        self.message = _FakeMsg()


def _patch_run_seams(monkeypatch, hits):
    """把 run() 的外部依赖都换成可控 fake，只保留 RAG→sources 这条主链路真实。"""
    from app.services import agent_service
    from app.llm.prompts.agent import AgentContext

    async def fake_search(db, **kw):
        return hits

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    async def fake_audit(*a, **k):
        return {"safe": True}

    monkeypatch.setattr("app.services.content_safety_service.audit_text", fake_audit)

    async def fake_ctx(db, user_id):
        return AgentContext(
            username="测试", grade="senior_1", subjects=["math"], streak_days=1,
            done_tasks=0, total_tasks=0, upcoming_exam_name=None, days_remaining=None,
            weakest_subject=None, learning_count=0, checkin_summary=None,
        )

    monkeypatch.setattr("app.services.agent_service.load_user_context", fake_ctx)

    async def fake_eps(db, **kw):
        return []

    monkeypatch.setattr("app.services.episodic_memory_service.retrieve_relevant", fake_eps)

    async def fake_classify(db, user_id, message):
        return ("simple", "")

    monkeypatch.setattr("app.services.planner_service.classify_complexity", fake_classify)

    async def fake_call_with_tools(**kw):
        return _FakeChoice()

    monkeypatch.setattr(agent_service.llm_client, "call_with_tools", fake_call_with_tools)

    async def fake_stream(**kw):
        for t in ["好", "的"]:
            yield t

    monkeypatch.setattr(agent_service.llm_client, "stream_response", fake_stream)

    async def fake_tts(*a, **k):
        return None

    monkeypatch.setattr("app.services.tts_service.synthesize", fake_tts)


async def _collect_done(monkeypatch, hits, message="2x的导数怎么求"):
    from app.services import agent_service

    _patch_run_seams(monkeypatch, hits)
    done = None
    async for line in agent_service.run(
        db=None, user_id=str(uuid.uuid4()), message=message, session_id=None
    ):
        if not line.startswith("data:"):
            continue
        payload = json.loads(line[len("data:"):].strip())
        if payload.get("done"):
            done = payload
    return done


@pytest.mark.asyncio
async def test_done_event_includes_rag_sources(monkeypatch):
    from app.services.rag_service import format_citations

    hits = [
        {"doc_kind": "mistake", "doc_id": "m1", "content": "题目：求2x导数",
         "score": 0.91, "metadata": {"title": "求2x导数"}},
        {"doc_kind": "note", "doc_id": "n1", "content": "导数的定义……",
         "score": 0.84, "metadata": {"title": "导数"}},
    ]
    done = await _collect_done(monkeypatch, hits)

    assert done is not None
    assert done["sources"] == format_citations(hits)
    assert done["sources"][0]["source_label"] == "错题"
    assert done["sources"][1]["source_label"] == "笔记"


@pytest.mark.asyncio
async def test_done_event_sources_empty_when_no_hits(monkeypatch):
    done = await _collect_done(monkeypatch, [])

    assert done is not None
    assert done["sources"] == []


@pytest.mark.asyncio
async def test_run_emits_rag_recall_observability(monkeypatch, caplog):
    """E 可观测：自动召回时发出 rag_recall 结构化埋点（含命中数 / 分布）。"""
    import logging

    hits = [
        {"doc_kind": "note", "doc_id": "n1", "content": "x", "score": 0.8, "metadata": {"title": "t"}},
    ]
    caplog.set_level(logging.INFO, logger="app.services.agent_service")
    await _collect_done(monkeypatch, hits)

    recall = [r.getMessage() for r in caplog.records if "rag_recall" in r.getMessage()]
    assert recall, "应发出 rag_recall 埋点日志"
    assert '"hit_count": 1' in recall[0]
    assert '"is_empty": false' in recall[0]
