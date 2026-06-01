# tests/unit/test_learning_engine.py
import pytest
from app.services.learning_engine import (
    recommend_actions, ActionType, RecommendedAction,
    select_difficulty, _apply_retrieval_preference, action_to_tool_call,
)


def _state(due=0, frontier=None, streak=0):
    return {
        "review_due": {"due": due},
        "knowledge_graph": {
            "total": 5, "mastered": 2, "learning": 3,
            "frontier": frontier or [],
        },
        "exams": {"next": None, "stress_level": "low"},
        "streak": streak,
    }


# ── 优先级顺序 ──

def test_due_flashcards_first():
    """到期闪卡 → 最高优先级（G-P2-1 优先级 1）"""
    acts = recommend_actions(_state(due=3))
    assert acts[0].action_type == ActionType.REVIEW_FLASHCARD
    assert "3" in acts[0].reason


def test_weak_frontier_fill_prerequisite():
    """前沿节点 p_mastery < 0.3 → FILL_PREREQUISITE（G-P2-1 优先级 2）"""
    frontier = [{"id": "kp1", "name": "极限", "p_mastery": 0.1}]
    acts = recommend_actions(_state(due=0, frontier=frontier))
    assert acts[0].action_type == ActionType.FILL_PREREQUISITE
    assert acts[0].params["kp_id"] == "kp1"
    assert "极限" in acts[0].reason


def test_due_before_fill_prerequisite():
    """到期复习 > 根因补漏"""
    frontier = [{"id": "kp1", "name": "极限", "p_mastery": 0.1}]
    types = [a.action_type for a in recommend_actions(_state(due=2, frontier=frontier))]
    assert types.index(ActionType.REVIEW_FLASHCARD) < types.index(ActionType.FILL_PREREQUISITE)


def test_healthy_frontier_explore():
    """前沿节点 p_mastery >= 0.3 → EXPLORE_FRONTIER（G-P2-1 优先级 3）"""
    frontier = [{"id": "kp2", "name": "导数", "p_mastery": 0.45}]
    types = [a.action_type for a in recommend_actions(_state(due=0, frontier=frontier))]
    assert ActionType.EXPLORE_FRONTIER in types
    assert ActionType.FILL_PREREQUISITE not in types


def test_practice_always_present():
    """PRACTICE（做题/回忆）总是在队列中（G-P2-3 提取优先）"""
    acts = recommend_actions(_state(due=0))
    assert any(a.action_type == ActionType.PRACTICE for a in acts)


def test_fill_before_explore():
    """弱节点(p<0.3) 在队列中先于 EXPLORE"""
    frontier = [
        {"id": "k1", "name": "极限", "p_mastery": 0.1},   # 弱
        {"id": "k2", "name": "导数", "p_mastery": 0.45},   # 就绪
    ]
    types = [a.action_type for a in recommend_actions(_state(due=0, frontier=frontier))]
    assert types.index(ActionType.FILL_PREREQUISITE) < types.index(ActionType.EXPLORE_FRONTIER)


# ── 兜底（G-P2-6）──

def test_fallback_empty_state():
    """完全空 state → 仍返回非空动作列表"""
    empty = {"review_due": {}, "knowledge_graph": {"frontier": []}, "exams": {}, "streak": 0}
    acts = recommend_actions(empty)
    assert len(acts) >= 1


def test_fallback_includes_practice():
    """兜底：无 KP 无复习 → 至少有 PRACTICE"""
    empty = {"review_due": {}, "knowledge_graph": {"frontier": []}, "exams": {}, "streak": 0}
    types = [a.action_type for a in recommend_actions(empty)]
    assert ActionType.PRACTICE in types


class TestSelectDifficulty:
    def test_high_correct_rate_upgrades_tier(self):
        r = select_difficulty(0.95, current_tier="blue")
        assert r["tier"] == "purple"
        assert r["should_fallback_to_prereq"] is False

    def test_cannot_upgrade_beyond_gold(self):
        r = select_difficulty(0.95, current_tier="gold")
        assert r["tier"] == "gold"

    def test_low_rate_downgrades_tier(self):
        r = select_difficulty(0.75, current_tier="purple")
        assert r["tier"] == "blue"
        assert r["should_fallback_to_prereq"] is False

    def test_low_rate_at_blue_flags_prereq_fallback(self):
        r = select_difficulty(0.75, current_tier="blue")
        assert r["tier"] == "blue"
        assert r["should_fallback_to_prereq"] is True

    def test_mid_range_rate_no_change(self):
        r = select_difficulty(0.85, current_tier="purple")
        assert r["tier"] == "purple"
        assert r["should_fallback_to_prereq"] is False

    def test_none_correct_rate_no_change(self):
        r = select_difficulty(None, current_tier="gold")
        assert r["tier"] == "gold"
        assert r["should_fallback_to_prereq"] is False


class TestRetrievalPreference:
    def test_practice_beats_expand_when_expand_has_lower_priority_num(self):
        actions = [
            RecommendedAction(action_type=ActionType.EXPAND, reason="x", priority=2),
            RecommendedAction(action_type=ActionType.PRACTICE, reason="y", priority=4),
        ]
        _apply_retrieval_preference(actions)
        sorted_acts = sorted(actions, key=lambda a: a.priority)
        types = [a.action_type for a in sorted_acts]
        assert types.index(ActionType.PRACTICE) < types.index(ActionType.EXPAND)

    def test_no_expand_in_list_is_noop(self):
        actions = [
            RecommendedAction(action_type=ActionType.PRACTICE, reason="y", priority=4),
        ]
        _apply_retrieval_preference(actions)  # must not raise
        assert actions[0].priority == 4


class TestActionToToolCall:
    def test_review_flashcard_routes_to_set_agent_state(self):
        a = RecommendedAction(ActionType.REVIEW_FLASHCARD, "复习", params={"due_count": 2})
        tool, args = action_to_tool_call(a)
        assert tool == "set_agent_state"
        assert args["state"] == "remind"

    def test_fill_prerequisite_routes_to_start_training(self):
        a = RecommendedAction(ActionType.FILL_PREREQUISITE, "补漏",
                              params={"kp_id": "abc-123", "kp_name": "极限"})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"
        assert "abc-123" in args["knowledge_point_ids"]
        assert args["difficulty_tiers"] == ["blue"]

    def test_explore_frontier_routes_to_start_training(self):
        a = RecommendedAction(ActionType.EXPLORE_FRONTIER, "探索",
                              params={"kp_id": "xyz", "kp_name": "导数"})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"

    def test_practice_routes_to_start_training(self):
        a = RecommendedAction(ActionType.PRACTICE, "练习", params={})
        tool, args = action_to_tool_call(a)
        assert tool == "start_training"
        assert args["question_count"] == 10
