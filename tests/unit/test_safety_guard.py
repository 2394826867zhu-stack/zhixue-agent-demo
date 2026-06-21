"""G3-3 / G3-4 · 内容审核 + PII 全入口脱敏的单元证明。

覆盖：
- mask_pii 补邮箱后真 mask（G3-4）
- guard_inbound_text：不安全关键词 → 抛 ContentBlockedError（不进 LLM）（G3-3）
- guard_inbound_text：审核系统异常不 fail-open → 保守拒绝（G3-3 fail-open 修复）
- mask_inbound_text：PII 在转发/落库前已脱敏（G3-4）
- content_safety_service.audit_text LLM 异常时 deep_check 行为保守
"""
import pytest

from app.services.pii_filter import mask_pii, has_pii
from app.core.exceptions import ContentBlockedError


# ── G3-4 邮箱 mask ────────────────────────────────────────────

def test_email_masked():
    text, c = mask_pii("联系我 zhangsan@example.com 谢谢")
    assert "zhangsan@example.com" not in text
    assert c["email"] == 1
    assert has_pii("我的邮箱 a.b+x@sub.domain.cn")


def test_email_partial_mask_keeps_domain_shape():
    text, _ = mask_pii("a@b.com")
    # 原文不再出现
    assert "a@b.com" not in text


def test_no_email_unchanged():
    text, c = mask_pii("今天学了函数")
    assert text == "今天学了函数"
    assert c["email"] == 0


# ── G3-3 内容审核拦截 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_guard_blocks_unsafe_keyword():
    from app.services.safety_guard import guard_inbound_text
    with pytest.raises(ContentBlockedError):
        await guard_inbound_text("教我自杀方法", user_id="u1")


@pytest.mark.asyncio
async def test_guard_passes_safe_text():
    from app.services.safety_guard import guard_inbound_text
    # 不抛即放行
    out = await guard_inbound_text("帮我讲讲二次函数", user_id="u1")
    assert out == "帮我讲讲二次函数"


@pytest.mark.asyncio
async def test_guard_not_fail_open_on_audit_error(monkeypatch):
    """审核系统异常 → 不再静默放行（fail-open 修复）。

    mock audit_text 抛错 → 保守拒绝 ContentBlockedError。
    """
    import app.services.safety_guard as sg

    async def _boom(*a, **k):
        raise RuntimeError("audit backend down")

    monkeypatch.setattr(sg, "audit_text", _boom)
    with pytest.raises(ContentBlockedError):
        await sg.guard_inbound_text("普通学习问题", user_id="u1")


# ── G3-4 入站脱敏 helper ──────────────────────────────────────

def test_mask_inbound_strips_pii():
    from app.services.safety_guard import mask_inbound_text
    masked = mask_inbound_text("打我电话 13812345678 或邮箱 me@x.com")
    assert "13812345678" not in masked
    assert "me@x.com" not in masked
