# tests/unit/test_search_service.py
"""C-09 全局搜索 · snippet 纯函数单测。"""
from app.services.search_service import _snippet


def test_snippet_returns_text():
    assert _snippet("hello world") == "hello world"


def test_snippet_none_and_empty():
    assert _snippet(None) is None
    assert _snippet("") is None
    assert _snippet("   ") is None


def test_snippet_truncates_with_ellipsis():
    s = _snippet("x" * 100, limit=80)
    assert s is not None and s.endswith("…")
    assert len(s) == 81  # 80 + 省略号


def test_snippet_collapses_whitespace():
    assert _snippet("a\n\n  b\tc") == "a b c"
