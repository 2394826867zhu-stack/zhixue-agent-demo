# tests/unit/test_p3_gain_integration.py
"""学习内核 P3 · 增益函数接入（G-P3-1 接入层）单元测试。

- graph_service.downstream_count：先修杠杆的下游可达计数（纯函数）。
- learning_engine.recommend_actions(use_gain=True)：用 gain_policy 重排前沿选择，
  use_gain 默认 False 时行为与 P2 完全一致（不破坏已绿优先级策略）。
"""
from app.services.graph_service import downstream_count
from app.services.learning_engine import recommend_actions, ActionType


# ── 先修杠杆：下游可达计数 ──

def test_downstream_count_counts_all_reachable():
    """a→b→c, a→d：a 下游={b,c,d}=3，b 下游={c}=1，叶子 c=0。"""
    edges = [("a", "b"), ("b", "c"), ("a", "d")]
    assert downstream_count("a", edges) == 3
    assert downstream_count("b", edges) == 1
    assert downstream_count("c", edges) == 0


def test_downstream_count_no_edges():
    assert downstream_count("x", []) == 0


def test_downstream_count_isolated_node():
    edges = [("a", "b")]
    assert downstream_count("z", edges) == 0


# ── recommend_actions use_gain 分支 ──

def _state(frontier):
    return {
        "review_due": {"due": 0},
        "knowledge_graph": {"frontier": frontier},
        "exams": {},
        "streak": 0,
    }


def test_use_gain_prefers_high_leverage_frontier():
    """两个就绪前沿：A 掌握度更低但叶子，B 掌握度略高但下游多（杠杆大）。
    - 默认(P2)：选掌握度最低的 A。
    - use_gain：选增益最高的 B（先修杠杆把它顶上来）。
    """
    frontier = [
        {"id": "A", "name": "甲", "p_mastery": 0.35, "downstream_count": 0},
        {"id": "B", "name": "乙", "p_mastery": 0.45, "downstream_count": 15},
    ]
    default = [a for a in recommend_actions(_state(frontier))
               if a.action_type == ActionType.EXPLORE_FRONTIER][0]
    assert default.params["kp_id"] == "A"

    gained = [a for a in recommend_actions(_state(frontier), use_gain=True)
              if a.action_type == ActionType.EXPLORE_FRONTIER][0]
    assert gained.params["kp_id"] == "B"


def test_use_gain_default_false_matches_p2():
    """use_gain 默认 False → 与 P2 行为一致（仍有 EXPLORE_FRONTIER）。"""
    frontier = [{"id": "A", "name": "甲", "p_mastery": 0.35, "downstream_count": 0}]
    acts = recommend_actions(_state(frontier))
    assert any(a.action_type == ActionType.EXPLORE_FRONTIER for a in acts)


def test_use_gain_weak_picks_highest_leverage_prereq():
    """弱前沿(p<0.3) 多个：use_gain 选下游最多的根因点补漏（杠杆优先）。"""
    frontier = [
        {"id": "W1", "name": "弱1", "p_mastery": 0.05, "downstream_count": 0},
        {"id": "W2", "name": "弱2", "p_mastery": 0.10, "downstream_count": 20},
    ]
    act = [a for a in recommend_actions(_state(frontier), use_gain=True)
           if a.action_type == ActionType.FILL_PREREQUISITE][0]
    assert act.params["kp_id"] == "W2"


def test_use_gain_missing_downstream_count_safe():
    """前沿节点缺 downstream_count → 兜底为 0，不崩。"""
    frontier = [{"id": "A", "name": "甲", "p_mastery": 0.4}]
    acts = recommend_actions(_state(frontier), use_gain=True)
    assert any(a.action_type == ActionType.EXPLORE_FRONTIER for a in acts)
