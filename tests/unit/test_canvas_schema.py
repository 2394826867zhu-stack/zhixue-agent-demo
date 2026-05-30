"""F-09 Canvas stroke schema 字段约束。

CanvasStrokeIn 的 color 原为裸 str（可注入任意字符串），path_d 仅有长度限制。
本测试驱动 color 的 hex 格式校验 + path_d 的 SVG 字符白名单。
"""
import pytest
from pydantic import ValidationError

from app.schemas.canvas import CanvasStrokeIn

_VALID_PATH = "M0 0 L10 10 C20 20 30 30 40 40 Z"


def test_stroke_rejects_non_hex_color():
    with pytest.raises(ValidationError):
        CanvasStrokeIn(path_d=_VALID_PATH, color="javascript:alert(1)")


def test_stroke_rejects_malformed_hex_color():
    # 5 位 hex 非法（合法为 3/4/6/8 位）
    with pytest.raises(ValidationError):
        CanvasStrokeIn(path_d=_VALID_PATH, color="#fffff")


@pytest.mark.parametrize("color", ["#fff", "#ffff", "#1F2937", "#1f2937ff"])
def test_stroke_accepts_valid_hex_color(color):
    s = CanvasStrokeIn(path_d=_VALID_PATH, color=color)
    assert s.color == color


def test_stroke_rejects_path_with_injection():
    with pytest.raises(ValidationError):
        CanvasStrokeIn(path_d="<script>alert(1)</script>", color="#000000")


def test_stroke_accepts_valid_svg_path():
    s = CanvasStrokeIn(path_d="M10.5,20.3 l-5,3 1e2 0", color="#000000")
    assert s.path_d.startswith("M")
