"""组卷强制题型格式规则（QA 走查实锤：choice 无格式约束 → 选择题不带选项）。"""
from app.llm.prompts.training_prompts import forced_type_clause


def test_choice_clause_mandates_four_options():
    c = forced_type_clause("choice")
    assert "choice" in c
    for opt in ("A. ", "B. ", "C. ", "D. "):
        assert opt in c, f"选择题格式规则须逐字给出选项格式（缺 {opt!r}）"


def test_true_false_clause_mandates_verdict_prefix():
    c = forced_type_clause("true_false")
    assert "正确" in c and "错误" in c


def test_all_eight_types_have_rules():
    for t in ("choice", "true_false", "fill_blank", "short_answer",
              "proof", "calculation", "essay", "programming"):
        c = forced_type_clause(t)
        assert "格式要求" in c, f"{t} 缺格式规则"


def test_unknown_type_degrades_gracefully():
    c = forced_type_clause("mystery")
    assert "mystery" in c and "格式要求" not in c
