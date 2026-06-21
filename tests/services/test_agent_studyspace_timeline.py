# tests/services/test_agent_studyspace_timeline.py
"""会话感知闭环：studyspace 模式下 run() 把回答/工具动作写入会话 timeline。

设计来源 spec 2026-06-21。

- LLM 流式回答 stub 成固定文本（隔离被测逻辑：只验证 timeline 写入，不依赖真实 LLM）。
- 用真实 db fixture 种 User + StudySpaceSession + CurriculumChapter，再查 timeline 确认落库。
- monkeypatch 模式复用 tests/unit/test_agent_engine_branch.py。
"""
import json
import uuid

import pytest

from app.models.user import User
from app.models.studyspace import StudySpaceSession
from app.models.curriculum import CurriculumChapter
from app.services.ss_timeline_service import ss_timeline_service

pytestmark = pytest.mark.asyncio

STUB_REPLY_TOKENS = ["这是", "知曜的", "回答"]
STUB_REPLY_TEXT = "".join(STUB_REPLY_TOKENS)


class _FakeMsg:
    content = "好的。"
    tool_calls = None

    def model_dump(self):
        return {}


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMsg()


def _stub_llm(monkeypatch):
    """把 run() 触达的所有外部依赖 stub 掉，LLM 流式回答固定为 STUB_REPLY_TEXT。"""
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
        for t in STUB_REPLY_TOKENS:
            yield t

    monkeypatch.setattr(agent_service.llm_client, "stream_response", fake_stream)

    async def fake_tts(*a, **k):
        return None

    monkeypatch.setattr("app.services.tts_service.synthesize", fake_tts)


async def _drain(gen):
    async for _ in gen:
        pass


async def _seed_ss_session(db) -> tuple[User, StudySpaceSession]:
    user = User(
        email=f"ss_tl_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="时间线测试",
    )
    db.add(user)
    await db.flush()

    chapter = CurriculumChapter(
        subject="math",
        grade_type="senior",
        grade_year=1,
        semester=1,
        chapter_index=1,
        chapter_title="导数",
        lesson_index=1,
        lesson_title="导数的定义",
    )
    db.add(chapter)
    await db.flush()

    ss = StudySpaceSession(
        user_id=user.id,
        chapter_id=chapter.id,
        session_type="lesson",
        status="active",
    )
    db.add(ss)
    await db.flush()
    return user, ss


async def test_run_writes_agent_message_node_in_studyspace(db, monkeypatch):
    """消费完 run(..., studyspace_session_id=<真实会话>) 后，timeline 出现 1 条 agent_message。"""
    _stub_llm(monkeypatch)
    user, ss = await _seed_ss_session(db)

    from app.services import agent_service

    await _drain(agent_service.run(
        db=db,
        user_id=str(user.id),
        message="什么是导数？",
        session_id=None,
        studyspace_session_id=str(ss.id),
    ))

    nodes = await ss_timeline_service.list_nodes(db, str(ss.id), str(user.id))
    agent_msgs = [n for n in nodes if n.kind == "agent_message"]
    assert len(agent_msgs) == 1, f"应有 1 条 agent_message，实际: {[n.kind for n in nodes]}"
    assert STUB_REPLY_TEXT in (agent_msgs[0].content or ""), \
        f"agent_message content 应含 stub 回答，实际: {agent_msgs[0].content!r}"


async def test_run_skips_timeline_when_no_studyspace_session(db, monkeypatch):
    """无 studyspace_session_id 时不崩、不抛。"""
    _stub_llm(monkeypatch)
    user = User(
        email=f"ss_tl_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="无会话测试",
    )
    db.add(user)
    await db.flush()

    from app.services import agent_service

    # 不抛即通过
    await _drain(agent_service.run(
        db=db,
        user_id=str(user.id),
        message="你好",
        session_id=None,
        studyspace_session_id=None,
    ))
