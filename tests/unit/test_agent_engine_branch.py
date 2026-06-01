# tests/unit/test_agent_engine_branch.py
"""G-P2-4: agent_service 引擎驱动分支测试。

验证：意图 = 学习推进 + engine enabled → 引擎选动作 → dispatch 工具 → done 带 decision 字段。
复用 test_agent_sources.py 的 monkeypatch 模式。
"""
import json
import uuid

import pytest


class _FakeMsg:
    content = "好的，为你安排了练习。"
    tool_calls = None

    def model_dump(self):
        return {}


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMsg()


def _base_patches(monkeypatch):
    """patch 所有与本测试无关的外部依赖。"""
    from app.services import agent_service
    from app.llm.prompts.agent import AgentContext

    async def fake_search(db, **kw):
        return []

    monkeypatch.setattr("app.services.rag_service.search", fake_search)

    async def fake_audit(*a, **k):
        return {"safe": True}

    monkeypatch.setattr("app.services.content_safety_service.audit_text", fake_audit)

    async def fake_ctx(db, user_id):
        return AgentContext(
            username="测试", grade="senior_1", subjects=["math"], streak_days=0,
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

    async def fake_dispatch(db, user_id, tool_name, arguments_json, **kw):
        return {"status": "ok", "tool": tool_name}

    monkeypatch.setattr("app.services.agent_service.dispatch_tool", fake_dispatch)


async def _collect_done(monkeypatch, message="帮我安排复习", extra_patches=None):
    from app.services import agent_service

    _base_patches(monkeypatch)
    if extra_patches:
        extra_patches(monkeypatch)
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
async def test_engine_branch_adds_decision_to_done(monkeypatch):
    """学习推进意图 → done 事件携带 decision 字段。"""
    _state = {
        "review_due": {"due": 2},
        "knowledge_graph": {"total": 3, "mastered": 1, "learning": 2, "frontier": []},
        "exams": {"next": None, "stress_level": "low"},
        "streak": 0,
    }

    async def fake_get_state(db, user_id):
        return _state

    monkeypatch.setattr("app.services.learner_state_service.get_learner_state", fake_get_state)

    done = await _collect_done(monkeypatch, message="帮我安排复习")
    assert done is not None
    assert "decision" in done, f"done 事件应包含 decision 字段，实际: {done}"
    assert done["decision"]["action"] == "review_flashcard"
    assert "reason" in done["decision"]


@pytest.mark.asyncio
async def test_engine_disabled_no_decision(monkeypatch):
    """LEARNING_ENGINE_ENABLED=False → done 不含 decision 字段（回退 ReAct）。"""
    from app import config as cfg
    monkeypatch.setattr(cfg, "settings", type("FakeSettings", (), {"LEARNING_ENGINE_ENABLED": False})())

    done = await _collect_done(monkeypatch, message="帮我安排复习")
    assert done is not None
    assert "decision" not in done


@pytest.mark.asyncio
async def test_free_chat_no_decision(monkeypatch):
    """自由聊天（非学习推进意图） → done 不含 decision 字段。"""
    done = await _collect_done(monkeypatch, message="什么是微分？")
    assert done is not None
    assert "decision" not in done


@pytest.mark.asyncio
async def test_engine_failure_falls_back_gracefully(monkeypatch):
    """learner_state_service 异常 → 引擎分支静默降级，对话仍正常完成。"""
    async def fail_get_state(db, user_id):
        raise RuntimeError("DB unavailable")

    monkeypatch.setattr("app.services.learner_state_service.get_learner_state", fail_get_state)

    done = await _collect_done(monkeypatch, message="帮我学高数")
    assert done is not None  # 对话必须完成，不能崩
