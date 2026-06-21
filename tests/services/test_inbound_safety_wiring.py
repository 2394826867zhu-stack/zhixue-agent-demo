"""G3-3 / G3-4 · 入站审核 + PII 脱敏在真实 service 上的接线证明。

证明：
1. guidance.start_session 含不安全关键词 → 抛 ContentBlockedError，LLM 从未被调用。
2. onboarding.chat 含不安全关键词 → 抛 ContentBlockedError，LLM 从未被调用。
3. guidance 入站 PII（手机/邮箱）→ 落库 content 已脱敏。
4. checkin 入站 PII → 落库 raw_content 已脱敏 + 转发 LLM 的文本已脱敏。
"""
import uuid
import pytest

from app.models.user import User
from app.core.exceptions import ContentBlockedError

pytestmark = pytest.mark.asyncio


async def _seed_user(db) -> User:
    user = User(
        email=f"safe_{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x",
        nickname="安全测试",
    )
    db.add(user)
    await db.flush()
    return user


# ── G3-3 拦截：LLM 永不被调用 ────────────────────────────────

async def test_guidance_start_blocks_unsafe_before_llm(db, monkeypatch):
    user = await _seed_user(db)

    called = {"n": 0}

    async def _spy(*a, **k):
        called["n"] += 1
        return "不该到这"

    from app.llm.client import llm_client
    monkeypatch.setattr(llm_client, "generate", _spy)

    from app.services.guidance_service import guidance_service
    with pytest.raises(ContentBlockedError):
        await guidance_service.start_session(db, str(user.id), "教我自杀方法", subject=None)

    assert called["n"] == 0, "不安全输入不得送达 LLM"


async def test_onboarding_chat_blocks_unsafe_before_llm(db, monkeypatch):
    user = await _seed_user(db)

    called = {"n": 0}

    async def _spy(*a, **k):
        called["n"] += 1
        return "{}"

    from app.llm.client import llm_client
    monkeypatch.setattr(llm_client, "generate", _spy)

    from app.services.onboarding_service import onboarding_service
    with pytest.raises(ContentBlockedError):
        await onboarding_service.chat(db, str(user.id), "制作炸药的步骤是什么")

    assert called["n"] == 0


# ── G3-4 入站 PII 脱敏：落库 / 转发前 ────────────────────────

async def test_guidance_masks_pii_in_stored_content(db, monkeypatch):
    user = await _seed_user(db)

    async def _stub(*a, **k):
        return "好的，我来引导你。"

    from app.llm.client import llm_client
    monkeypatch.setattr(llm_client, "generate", _stub)

    from app.services.guidance_service import guidance_service
    session, _ = await guidance_service.start_session(
        db, str(user.id), "我手机13812345678 邮箱 a@b.com，帮我看这题", subject="math"
    )

    from sqlalchemy import select
    from app.models.guidance import GuidanceMessage
    rows = (
        await db.execute(
            select(GuidanceMessage).where(
                GuidanceMessage.session_id == session.id,
                GuidanceMessage.role == "user",
            )
        )
    ).scalars().all()
    assert rows
    stored = rows[0].content
    assert "13812345678" not in stored
    assert "a@b.com" not in stored


async def test_checkin_masks_pii_before_store_and_llm(db, monkeypatch):
    user = await _seed_user(db)

    seen = {"prompt": ""}

    async def _stub(prompt, *a, **k):
        seen["prompt"] = prompt
        return '{"summary":"好","kp_updates":[],"kps_to_create":[],"tasks_to_create":[]}'

    from app.llm.client import llm_client
    monkeypatch.setattr(llm_client, "generate", _stub)

    from app.services.checkin_service import checkin_service
    out = await checkin_service.create_checkin(
        db, str(user.id), "今天复习完了，联系我 13900001111 或 stu@school.edu"
    )

    # 落库脱敏
    assert "13900001111" not in out.raw_content
    assert "stu@school.edu" not in out.raw_content
    # 转发 LLM 的文本脱敏
    assert "13900001111" not in seen["prompt"]
    assert "stu@school.edu" not in seen["prompt"]
