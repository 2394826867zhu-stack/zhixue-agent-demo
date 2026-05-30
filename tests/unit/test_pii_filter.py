"""v0.31 · PII filter 单测"""
from app.services.pii_filter import mask_pii, has_pii


def test_phone_masked():
    text, c = mask_pii("我电话是 13812345678 联系我")
    assert "138****5678" in text or "13812345678" not in text
    assert c["phone"] == 1


def test_id_card_masked():
    text, c = mask_pii("我的身份证 110101199001011234 你看")
    # 18 位拆分：6 行政码 + 8 日期 + 4 序+校验 → 中间 8 位 mask 成 ********
    assert "110101********1234" in text
    assert "199001011234" not in text
    assert c["id_card"] == 1


def test_no_pii_unchanged():
    text, c = mask_pii("今天数学怎么样")
    assert text == "今天数学怎么样"
    assert sum(c.values()) == 0


def test_has_pii():
    assert has_pii("打 13812345678")
    assert not has_pii("今天怎么样")
