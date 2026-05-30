"""v0.31 Safety · Q18 锁定 · 正则 PII mask

入站：用户消息中的身份证 / 手机号 / 银行卡 → mask 后再喂给 LLM
出站：LLM 回复如带 PII 也 mask（防 prompt-injection 让 LLM 反吐用户敏感信息）
"""
import re

# 中国大陆身份证 18 位
_ID_CARD = re.compile(r"(?<!\d)([1-9]\d{5})(\d{8})(\d{3}[0-9xX])(?!\d)")
# 中国大陆手机号 11 位（13-19 开头）
_PHONE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
# 银行卡 16-19 位（粗略）
_BANK_CARD = re.compile(r"(?<!\d)(\d{4})\d{8,11}(\d{4})(?!\d)")


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """返回 (masked_text, counts) — counts 含每类 PII 匹配数"""
    if not text:
        return text, {"id_card": 0, "phone": 0, "bank_card": 0}
    counts = {"id_card": 0, "phone": 0, "bank_card": 0}

    def _id(m):
        counts["id_card"] += 1
        return m.group(1) + "********" + m.group(3)

    def _ph(m):
        counts["phone"] += 1
        return m.group(1) + "****" + m.group(3)

    def _bc(m):
        counts["bank_card"] += 1
        return m.group(1) + "*" * 8 + m.group(2)

    text = _ID_CARD.sub(_id, text)
    text = _PHONE.sub(_ph, text)
    text = _BANK_CARD.sub(_bc, text)
    return text, counts


def has_pii(text: str) -> bool:
    if not text:
        return False
    return bool(_ID_CARD.search(text) or _PHONE.search(text) or _BANK_CARD.search(text))
