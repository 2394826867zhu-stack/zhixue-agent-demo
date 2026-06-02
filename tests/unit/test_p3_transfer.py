# tests/unit/test_p3_transfer.py
"""学习内核 P3 · 迁移挑战进策略（G-P3-4，[M9]）单元测试。

掌握度达阈的节点 → 引擎主动产出迁移挑战动作（换皮新题验证真懂还是背的），
对应设计§3.2 优先级④交错/迁移挑战。
"""
from app.services.learning_engine import (
    recommend_actions, ActionType, RecommendedAction, action_to_tool_call,
)


def _state(transfer=None, frontier=None, due=0):
    return {
        "review_due": {"due": due},
        "knowledge_graph": {
            "frontier": frontier or [],
            "transfer_candidates": transfer or [],
        },
        "exams": {},
        "streak": 0,
    }


def test_transfer_challenge_emitted_for_mastered():
    transfer = [{"id": "m1", "name": "导数", "p_mastery": 0.88}]
    acts = recommend_actions(_state(transfer=transfer))
    t = [a for a in acts if a.action_type == ActionType.TRANSFER_CHALLENGE]
    assert len(t) == 1
    assert t[0].params["kp_id"] == "m1"
    assert "迁移" in t[0].reason or "换" in t[0].reason


def test_no_transfer_when_empty():
    acts = recommend_actions(_state(transfer=[]))
    assert not any(a.action_type == ActionType.TRANSFER_CHALLENGE for a in acts)


def test_transfer_before_practice():
    """优先级：迁移挑战(③级) 排在 PRACTICE 之前。"""
    transfer = [{"id": "m1", "name": "导数", "p_mastery": 0.9}]
    frontier = [{"id": "f1", "name": "积分", "p_mastery": 0.4}]
    types = [a.action_type for a in recommend_actions(_state(transfer=transfer, frontier=frontier))]
    assert types.index(ActionType.TRANSFER_CHALLENGE) < types.index(ActionType.PRACTICE)


def test_transfer_alone_is_signal():
    """只有 transfer_candidates（无前沿无复习）→ 仍产出迁移挑战，不走兜底。"""
    acts = recommend_actions(_state(transfer=[{"id": "m1", "name": "x", "p_mastery": 0.85}]))
    assert any(a.action_type == ActionType.TRANSFER_CHALLENGE for a in acts)


def test_action_to_tool_call_transfer_routes_to_gold_training():
    a = RecommendedAction(ActionType.TRANSFER_CHALLENGE, "迁移",
                          params={"kp_id": "m1", "kp_name": "导数"})
    tool, args = action_to_tool_call(a)
    assert tool == "start_training"
    assert "m1" in args["knowledge_point_ids"]
    assert args["difficulty_tiers"] == ["gold"]
