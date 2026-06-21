# tests/services/test_agent_studyspace_tool_inject.py
"""会话感知闭环 · ss_session_id 注入：studyspace 模式下 run() 的工具循环
必须把会话 UUID 注入 ss-aware 工具（set_lesson_plan / spot_quiz / feynman_grade）的 args，
否则 handler 拿到 ss_session_id=None 静默 no-op（lesson_plan 永不写）。

真 bug 复现：LLM 生成的 set_lesson_plan tool_call args 里**不含** ss_session_id
（LLM 不知道这个服务端 UUID）→ 修前 ss.lesson_plan 恒为 None。

- 用真实 db fixture 种 User + StudySpaceSession + CurriculumChapter。
- LLM stub 首轮返回 set_lesson_plan(steps=[...])（args 无 ss_session_id），第二轮 stop 收尾。
- dispatch_tool **不 stub**（真跑 _set_lesson_plan，才能验证落库）。
- 断言 ss.lesson_plan["steps"] 被写入 + current_index=0。
  修前 FAIL（lesson_plan is None），修后 PASS。

monkeypatch 模式复用 tests/services/test_agent_studyspace_timeline.py。
"""
import json
import uuid

import pytest

from app.models.user import User
from app.models.studyspace import StudySpaceSession
from app.models.curriculum import CurriculumChapter
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

PLAN_STEPS = ["导数的定义", "几何意义", "求导法则", "应用举例"]


class _FakeMsg:
    content = "好的，我们开始这一课。"
    tool_calls = None

    def model_dump(self):
        return {}


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMsg()


class _FakeFn:
    """tool_call.function：name + 任意 arguments JSON 串（模拟真实 LLM 输出）。"""

    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, idx, name, arguments):
        self.id = f"call_{idx}"
        self.function = _FakeFn(name, arguments)


class _FakeToolMsg:
    content = None

    def __init__(self, calls):
        # calls: list[(name, arguments_json)]
        self.tool_calls = [
            _FakeToolCall(i, n, a) for i, (n, a) in enumerate(calls)
        ]

    def model_dump(self):
        return {}


class _FakeToolChoice:
    finish_reason = "tool_calls"

    def __init__(self, calls):
        self.message = _FakeToolMsg(calls)


def _stub_llm_env(monkeypatch):
    """把 run() 触达的所有外部依赖 stub 掉，只保留 dispatch_tool 真实运行。"""
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

    async def fake_stream(**kw):
        for t in ["好", "的"]:
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
        email=f"ss_inj_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="注入测试",
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


async def test_run_injects_ss_session_id_into_set_lesson_plan(db, monkeypatch):
    """LLM 返回 set_lesson_plan(steps=[...])（args 不含 ss_session_id）→
    run() 工具循环注入会话 UUID → ss.lesson_plan 真落库（steps + current_index=0）。

    修前 FAIL：dispatch_tool 只收 LLM 的 args（无 ss_session_id），
    _set_lesson_plan 静默 no-op，ss.lesson_plan 恒为 None。
    """
    _stub_llm_env(monkeypatch)
    user, ss = await _seed_ss_session(db)
    await db.commit()

    from app.services import agent_service

    # 模拟真实 LLM：set_lesson_plan args 只有 steps，**没有** ss_session_id
    llm_args = json.dumps({"steps": PLAN_STEPS}, ensure_ascii=False)
    _calls = [
        _FakeToolChoice([("set_lesson_plan", llm_args)]),  # 首轮：调工具
        _FakeChoice(),                                      # 第二轮：stop 收尾
    ]

    async def fake_call_with_tools(**kw):
        return _calls.pop(0)

    monkeypatch.setattr(agent_service.llm_client, "call_with_tools", fake_call_with_tools)

    await _drain(agent_service.run(
        db=db,
        user_id=str(user.id),
        message="老师我们开始上这一课吧",
        session_id=None,
        studyspace_session_id=str(ss.id),
    ))

    # 独立 session 复查：证明 lesson_plan 真 commit 落库
    async with TestSessionLocal() as fresh:
        reloaded = await fresh.get(StudySpaceSession, ss.id)
        plan = reloaded.lesson_plan

    assert plan is not None, "ss.lesson_plan 应被写入（修前为 None = bug）"
    # handler 会 strip + 截 40 字符；这里 steps 都短，等值即可
    assert plan["steps"] == PLAN_STEPS, f"lesson_plan.steps 应等于 LLM 给的 steps，实际: {plan}"
    assert plan["current_index"] == 0, f"lesson_plan.current_index 应为 0，实际: {plan}"


async def test_run_does_not_inject_for_non_ss_tools(db, monkeypatch):
    """注入只针对 3 个 ss-aware 工具；普通工具（generate_note）args 不被改动、不报错。

    锁住「仅对 ss-aware 工具注入」——其他工具 handler 无 ss_session_id 形参，
    误注入会因无 **_ 报错。这里走真 dispatch（generate_note handler 被 stub）。
    """
    _stub_llm_env(monkeypatch)
    user, ss = await _seed_ss_session(db)
    await db.commit()

    from app.services import agent_service

    seen_args = {}

    async def fake_dispatch(db_, uid, name, arguments_json, **kw):
        seen_args[name] = arguments_json
        return {"ok": True, "tool": name}

    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch)

    _calls = [
        _FakeToolChoice([("generate_note", json.dumps({"topic": "导数"}))]),
        _FakeChoice(),
    ]

    async def fake_call_with_tools(**kw):
        return _calls.pop(0)

    monkeypatch.setattr(agent_service.llm_client, "call_with_tools", fake_call_with_tools)

    await _drain(agent_service.run(
        db=db,
        user_id=str(user.id),
        message="给我生成一份笔记",
        session_id=None,
        studyspace_session_id=str(ss.id),
    ))

    parsed = json.loads(seen_args["generate_note"])
    assert "ss_session_id" not in parsed, \
        f"非 ss-aware 工具不应被注入 ss_session_id，实际: {parsed}"
