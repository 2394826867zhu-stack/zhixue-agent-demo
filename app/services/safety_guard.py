"""G3-3 / G3-4 · 入站文本安全统一入口（审计 P0 · 未成年人产品）。

所有「用户自由文本 → 落库 / 转发外部 LLM」的 service 入站处都应过这两个 helper：

- `mask_inbound_text(text)`：PII 脱敏（身份证/手机/银行卡/邮箱），落库与转发前调用。
- `guard_inbound_text(text, user_id)`：内容审核闸——命中不安全关键词抛 ContentBlockedError
  （调用方不再继续送 LLM）；**审核系统异常时保守拒绝（不 fail-open）**。

为什么不 fail-open：面向中学生的产品，审核后端异常时宁可拒一条正常消息，
也不能让自残/暴力/色情内容静默穿透到 LLM。历史 bug：agent_service 的
`except` 静默 `pass` 放行（G3-3 审计发现）。
"""
import logging

from app.core.exceptions import ContentBlockedError
from app.services.content_safety_service import audit_text, make_redirect_reply
from app.services.pii_filter import mask_pii

logger = logging.getLogger(__name__)


def mask_inbound_text(text: str | None) -> str | None:
    """G3-4 · 入站 PII 脱敏。失败时返回原文（mask 是纯正则，理论不抛；
    若真抛了也不该因脱敏失败丢业务，但记 warning 暴露）。"""
    if not text:
        return text
    try:
        masked, counts = mask_pii(text)
        if any(counts.values()):
            logger.info("pii_masked inbound: %s", counts)
        return masked
    except Exception as e:  # pragma: no cover - 正则不应抛
        logger.warning("mask_inbound_text failed, passthrough: %s", e)
        return text


async def guard_inbound_text(
    text: str | None, user_id: str | None = None, deep_check: bool = False
) -> str:
    """G3-3 · 内容审核闸。

    - 安全 → 返回原文（调用方继续）。
    - 命中不安全 → 抛 ContentBlockedError（调用方停止，不送 LLM）。
    - 审核系统异常 → **保守拒绝**（抛 ContentBlockedError），不 fail-open。

    deep_check=False 时只跑确定性关键词黑名单（零 LLM 成本），已能拦最严重违规。
    """
    if not text or not text.strip():
        return text or ""
    try:
        result = await audit_text(text, deep_check=deep_check, user_id=user_id)
    except Exception as e:
        # fail-closed：审核不可用对未成年人产品 = 保守拒绝
        logger.error(
            "content_safety audit FAILED (fail-closed, blocking) user=%s: %s",
            user_id, e,
        )
        raise ContentBlockedError() from e

    if not result.get("safe", False):
        logger.info(
            "content_safety blocked inbound user=%s cat=%s by=%s",
            user_id, result.get("category"), result.get("blocked_by"),
        )
        err = ContentBlockedError()
        # 引导式劝退文案（调用方若想返回友好提示可读 .message）
        err.message = make_redirect_reply(result.get("category"))
        raise err
    return text
