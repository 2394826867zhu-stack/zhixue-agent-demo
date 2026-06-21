"""set_lesson_plan 工具：知曜开场把「3-5 核心概念框架」落成 lesson_plan（plan Task A3）。

知曜在 StudySpace 教学开场调用 set_lesson_plan(steps=[概念名...])，把分步框架写入
当前会话的 `lesson_plan` JSONB（{steps, current_index:0}）喂前端 PathStepper。

dispatch_tool 拿 ss_session_id 的方式与 spot_quiz / feynman_grade 一致——
不是 dispatch_tool 的独立参数，而是经 `**args` 透传（LLM 把 ss_session_id 放进
工具 arguments，前端在 SS 模式自动注入）。本测试照此把 ss_session_id 放进
arguments JSON。
"""
import json
import uuid

import pytest

from app.models.user import User
from app.models.curriculum import CurriculumChapter
from app.models.studyspace import StudySpaceSession

pytestmark = pytest.mark.asyncio


async def _seed_lesson_session(db) -> tuple[User, StudySpaceSession]:
    user = User(
        email=f"set_lesson_plan_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="教学开场测试",
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


async def test_set_lesson_plan_writes_session_field(db):
    from app.services.agent_tools import dispatch_tool

    user, ss = await _seed_lesson_session(db)

    res = await dispatch_tool(
        db,
        str(user.id),
        "set_lesson_plan",
        json.dumps(
            {
                "steps": ["导数定义", "用导数判断增减", "极值点"],
                "ss_session_id": str(ss.id),
            },
            ensure_ascii=False,
        ),
    )

    assert res.get("ok") is True
    await db.refresh(ss)
    assert ss.lesson_plan["steps"] == ["导数定义", "用导数判断增减", "极值点"]
    assert ss.lesson_plan["current_index"] == 0
