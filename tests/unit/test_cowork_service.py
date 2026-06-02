"""E-12 · Cowork 纯函数单测。"""
from app.services import cowork_service as cw


def test_gen_code_format():
    c = cw.gen_code()
    assert len(c) == 6
    assert all(ch in cw._ALPHABET for ch in c)
    # 去易混字符
    assert not (set(c) & set("01OIL"))


def test_normalize_state():
    assert cw.normalize_state("focusing") == "focusing"
    assert cw.normalize_state("break") == "break"
    assert cw.normalize_state("idle") == "idle"
    assert cw.normalize_state("weird") == "idle"
    assert cw.normalize_state(None) == "idle"
