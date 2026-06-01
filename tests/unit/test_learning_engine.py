# tests/unit/test_learning_engine.py
import pytest
from app.services.learning_engine import (
    recommend_actions, ActionType, RecommendedAction,
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
