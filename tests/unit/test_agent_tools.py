import uuid

import pytest

from app.models.knowledge_point import KnowledgePoint
from app.models.user import User
from app.services import agent_service
from app.services.onboarding_service import onboarding_service
from app.services.agent_tools import dispatch_tool


@pytest.mark.asyncio
async def test_agent_plan_study_schedule_creates_tasks(db):
    user_id = str(uuid.uuid4())
    db.add(
        User(
            id=uuid.UUID(user_id),
            email=f"{user_id}@example.com",
            password_hash="test-hash",
        )
    )
    await db.flush()
    db.add(
        KnowledgePoint(
            user_id=uuid.UUID(user_id),
            name="函数单调性",
            subject="数学",
            mastery_status="learning",
            bloom_level="understand",
        )
    )
    await db.commit()

    result = await dispatch_tool(
        db,
        user_id,
        "plan_study_schedule",
        '{"subjects":["数学"],"days_ahead":3,"goal":"期末复习"}',
    )

    assert "error" not in result
    assert result["total"] == 1
    assert result["created_tasks"][0]["subject"] == "数学"


@pytest.mark.asyncio
async def test_onboarding_extract_uses_local_fallback_when_llm_fails(monkeypatch):
    async def fail_generate(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.services.onboarding_service.llm_client.generate", fail_generate)

    grade = await onboarding_service._extract("grade", "我现在高二", {})
    subjects = await onboarding_service._extract("subjects", "数学、英语和物理要重点提升", {})
    progress = await onboarding_service._extract(
        "progress",
        "数学学到导数，英语在学必修二，物理刚开始电场",
        {"subjects": ["数学", "英语", "物理"]},
    )
    performance = await onboarding_service._extract(
        "performance",
        "数学中等，英语不错，物理比较差",
        {"subjects": ["数学", "英语", "物理"]},
    )

    assert grade == {"grade": "高二", "grade_type": "senior"}
    assert subjects == {"subjects": ["数学", "英语", "物理"]}
    assert progress["progress"]["数学"] == "导数"
    assert performance["performance"]["英语"] == "良好"
    assert performance["performance"]["物理"] == "较差"


@pytest.mark.asyncio
async def test_onboarding_extract_falls_back_when_llm_returns_empty(monkeypatch):
    async def empty_generate(*args, **kwargs):
        return "{}"

    monkeypatch.setattr("app.services.onboarding_service.llm_client.generate", empty_generate)

    performance = await onboarding_service._extract(
        "performance",
        "中等",
        {"subjects": ["数学", "英语", "物理"]},
    )

    assert performance == {"performance": {"数学": "中等", "英语": "中等", "物理": "中等"}}


@pytest.mark.asyncio
async def test_agent_history_is_scoped_by_user(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.values = {}

        async def get(self, key):
            return self.values.get(key)

        async def setex(self, key, ttl, value):
            self.values[key] = value

    fake = FakeRedis()

    async def get_fake_redis():
        return fake

    monkeypatch.setattr(agent_service, "get_redis", get_fake_redis)

    await agent_service.save_history("user-a", "same-session", [{"role": "user", "content": "A"}])
    await agent_service.save_history("user-b", "same-session", [{"role": "user", "content": "B"}])

    assert await agent_service.load_history("user-a", "same-session") == [{"role": "user", "content": "A"}]
    assert await agent_service.load_history("user-b", "same-session") == [{"role": "user", "content": "B"}]
