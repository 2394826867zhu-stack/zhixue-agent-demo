"""INC-B 学科两层分类法 + 领域模板 单测（纯逻辑，无 DB）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §6
"""
from app.services.subject_taxonomy import (
    parse_category, domain_template_for, to_canonical, map_free_text,
    CAT_STEM, CAT_CS, CAT_LANGUAGE, CAT_HUMANITIES, CAT_CUSTOM,
    DOMAIN_TEMPLATES, GENERIC_TEMPLATE,
)


def test_parse_category_new_format():
    assert parse_category("数理科学 > 数学") == CAT_STEM
    assert parse_category("计算机与工程 > 人工智能/机器学习") == CAT_CS
    assert parse_category("自定义 > 船舶工程") == CAT_CUSTOM


def test_parse_category_legacy_freestring():
    # 兼容存量 27 项 flat SUBJECTS（无需数据迁移，读时推断）
    assert parse_category("数学") == CAT_STEM
    assert parse_category("高等数学") == CAT_STEM
    assert parse_category("Python") == CAT_CS
    assert parse_category("数据结构") == CAT_CS
    assert parse_category("考研英语") == CAT_LANGUAGE
    assert parse_category("历史") == CAT_HUMANITIES


def test_parse_category_unknown_to_custom():
    assert parse_category("船舶工程") == CAT_CUSTOM
    assert parse_category(None) == CAT_CUSTOM
    assert parse_category("") == CAT_CUSTOM
    assert parse_category("   ") == CAT_CUSTOM


def test_domain_template_drives_shape():
    # 大类 → 领域结构骨架（D8：大类参与定形）
    assert domain_template_for("数理科学 > 数学") == DOMAIN_TEMPLATES[CAT_STEM]
    assert domain_template_for("语文") == DOMAIN_TEMPLATES[CAT_LANGUAGE]
    # 自定义/未知 → 通用骨架（不崩）
    assert domain_template_for("船舶工程") == GENERIC_TEMPLATE
    assert domain_template_for(None) == GENERIC_TEMPLATE


def test_to_canonical_format_and_custom_limit():
    assert to_canonical("数理科学", "数学") == "数理科学 > 数学"
    # 非法大类 → 自定义
    assert to_canonical("乱写大类", "X").startswith(CAT_CUSTOM + " > ")
    # 自定义细分 ≤30 字
    out = to_canonical(CAT_CUSTOM, "天" * 40)
    assert len(out.split(">", 1)[1].strip()) <= 30


def test_map_free_text_canonical():
    # 大类推断正确 + 规范格式（spec §10.2 示例）
    assert map_free_text("考研数学").startswith("数理科学 > ")
    assert parse_category(map_free_text("学Python")) == CAT_CS
    assert parse_category(map_free_text("法律")) == CAT_HUMANITIES
    # 已规范格式原样返回
    assert map_free_text("数理科学 > 数学") == "数理科学 > 数学"
    # 无法映射 → 自定义 > 原话
    assert map_free_text("船舶工程").startswith(CAT_CUSTOM + " > ")
    # 空 → None
    assert map_free_text("") is None
    assert map_free_text(None) is None
