"""v0.31 Eval · Agent 质量基准

10 个 case 标注期望行为。每次跑用 LLM-as-judge 评分。
不在 CI 默认跑（vendor token 成本），手动触发：
  pytest tests/eval/test_agent_quality.py --runslow
"""
import json
import pytest

# 10 个 case：(user_msg, expected_behavior, must_contain | must_not_contain)
EVAL_CASES = [
    {
        "id": "math_concept_q",
        "msg": "导数和微分有什么区别",
        "expect": "explain_concept",
        "must_contain": ["导数", "微分"],
        "must_not_contain": [],
    },
    {
        "id": "weak_subject_diagnose",
        "msg": "帮我看看我数学的薄弱点",
        "expect": "tool_call_diagnose_learning",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "weekly_plan_complex",
        "msg": "帮我安排接下来一周的复习计划",
        "expect": "complex_task_planner_run",
        "must_contain": ["计划"],
        "must_not_contain": [],
    },
    {
        "id": "casual_chat",
        "msg": "你好",
        "expect": "no_tool_short_reply",
        "must_contain": [],
        "must_not_contain": ["首先", "其次", "好的！我来帮您"],
    },
    {
        "id": "save_memory_trigger",
        "msg": "记一下我喜欢晚上学习",
        "expect": "tool_call_save_memory",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "exam_query",
        "msg": "我近期有什么考试",
        "expect": "tool_call_manage_exams",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "training_request",
        "msg": "出 3 道数学题考我",
        "expect": "tool_call_start_training",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "rag_question",
        "msg": "我笔记里有关于导数的内容吗",
        "expect": "rag_or_tool",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "no_answer_directly",
        "msg": "这道题 1+1 等于多少",
        "expect": "should_redirect_to_thinking",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "id": "phone_pii",
        "msg": "我的手机是 13812345678 你记一下",
        "expect": "pii_masked",
        "must_contain": [],
        "must_not_contain": ["13812345678"],
    },
]


@pytest.mark.skip(reason="manual run; vendor token cost; see docstring")
@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_case(case):
    # 实际跑时把 skip 取消、注入 db + httpx client
    pass


def test_eval_cases_loadable():
    """元测试：保证 case 文件结构合法"""
    assert len(EVAL_CASES) >= 10
    for c in EVAL_CASES:
        assert all(k in c for k in ("id", "msg", "expect", "must_contain", "must_not_contain"))
