# app/services/learning_engine.py
"""学习内核 P2 · 策略脊柱（learning_engine）。

确定性优先级策略，把"做什么"的决策权从 LLM 收归到引擎。
纯函数，零 DB、零 IO，便于 TDD。
设计见《知曜学习内核_设计.md》§3.2。

优先级（高 → 低）：
  1. REVIEW_FLASHCARD  — FSRS 到期复习
  2. FILL_PREREQUISITE — 根因补漏（先修 p_mastery < WEAK_THRESHOLD）
  3. EXPLORE_FRONTIER  — 前沿新点（先修就绪）
  4. PRACTICE          — 做题/回忆（M4 提取优先）
  5. EXPAND            — 拓展阅读（被 PRACTICE 排后）

兜底（G-P2-6）：state 不全/策略给不出 → FSRS 到期 + 前沿新点，绝不空转。
"""
from __future__ import annotations

from dataclasses import dataclass, field


class ActionType:
    REVIEW_FLASHCARD = "review_flashcard"
    FILL_PREREQUISITE = "fill_prerequisite"
    EXPLORE_FRONTIER = "explore_frontier"
    PRACTICE = "practice"
    EXPAND = "expand"


@dataclass
class RecommendedAction:
    action_type: str
    reason: str
    params: dict = field(default_factory=dict)
    priority: int = 0  # 数字越小优先级越高


_WEAK_THRESHOLD = 0.3
_DIFFICULTY_TIERS = ("blue", "purple", "gold")
_GAIN_EST_MINUTES = 10.0  # 前沿动作单次耗时估计（gain 接入用，分钟）


# ─── P3 增益接入（G-P3-1）：把前沿候选按 gain_policy 重排 ────────────────────


def _frontier_to_candidate(node: dict) -> dict:
    """前沿节点 dict → gain_policy 候选契约（缺字段走 gain_policy 中性兜底）。"""
    return {
        "kp_id": node.get("id", ""),
        "p_mastery": node.get("p_mastery", 0.0),
        "downstream_count": node.get("downstream_count", 0),
        "stability": node.get("stability"),
        "last_reviewed_at": node.get("last_reviewed_at"),
        "recent_correct_rate": node.get("recent_correct_rate"),
        "est_minutes": _GAIN_EST_MINUTES,
    }


def _rank_frontier_by_gain(nodes: list[dict]) -> list[dict]:
    """按 gain_policy 单位时间增益降序重排前沿节点（保留原 node dict）。"""
    from app.services.gain_policy import rank_candidates
    by_id = {n.get("id", ""): n for n in nodes}
    ranked = rank_candidates([_frontier_to_candidate(n) for n in nodes])
    return [by_id[c["kp_id"]] for c in ranked if c.get("kp_id") in by_id]


# ─── 主策略（G-P2-1 + G-P3-1 增益接入）──────────────────────────────────────


def recommend_actions(learner_state: dict, *, use_gain: bool = False) -> list[RecommendedAction]:
    """给定学习者状态，返回有序动作队列（纯函数，不含 DB）。

    use_gain=False（默认）：P2 确定性优先级（前沿选掌握度最低）。
    use_gain=True（G-P3-1，feature flag `LEARNING_GAIN_ENABLED`）：前沿候选改按
      gain_policy 单位时间增益排序——先修杠杆/遗忘/ZPD 综合最高者优先。
    """
    if not isinstance(learner_state, dict):
        learner_state = {}

    due_count = learner_state.get("review_due", {}).get("due", 0)
    frontier = learner_state.get("knowledge_graph", {}).get("frontier", [])
    weak = [n for n in frontier if n.get("p_mastery", 0.0) < _WEAK_THRESHOLD]
    non_weak = [n for n in frontier if n.get("p_mastery", 0.0) >= _WEAK_THRESHOLD]
    if use_gain:
        # P3：按单位时间增益排序（杠杆高的根因点/前沿点顶上来）
        weak = _rank_frontier_by_gain(weak)
        non_weak = _rank_frontier_by_gain(non_weak)
    else:
        # P2：non_weak 按掌握度升序，引擎挑最低掌握的前沿（Fix 3）
        non_weak.sort(key=lambda n: n.get("p_mastery", 0.0))

    has_signal = due_count > 0 or bool(weak) or bool(non_weak)
    if not has_signal:
        return _fallback_actions(learner_state)

    actions: list[RecommendedAction] = []

    if due_count > 0:
        actions.append(RecommendedAction(
            action_type=ActionType.REVIEW_FLASHCARD,
            reason=f"你有 {due_count} 张闪卡到期，现在复习可强化记忆",
            params={"due_count": due_count},
            priority=1,
        ))

    if weak:
        # use_gain 时 weak 已按 gain 降序，[0] 即最高杠杆根因点；否则取掌握度最低
        target = weak[0] if use_gain else min(weak, key=lambda n: n.get("p_mastery", 0.0))
        actions.append(RecommendedAction(
            action_type=ActionType.FILL_PREREQUISITE,
            reason=f"建议先巩固「{target.get('name', '')}」（掌握度 {target.get('p_mastery', 0):.0%}），这是后续知识的地基",
            params={"kp_id": target.get("id", ""), "kp_name": target.get("name", "")},
            priority=2,
        ))

    if non_weak:
        target = non_weak[0]
        actions.append(RecommendedAction(
            action_type=ActionType.EXPLORE_FRONTIER,
            reason=f"推荐学习「{target.get('name', '')}」，你的先修知识已就绪",
            params={"kp_id": target.get("id", ""), "kp_name": target.get("name", "")},
            priority=3,
        ))

    actions.append(RecommendedAction(
        action_type=ActionType.PRACTICE,
        reason="做一组练习题，用提取练习强化已学内容",
        params={},
        priority=4,
    ))

    _apply_retrieval_preference(actions)
    return sorted(actions, key=lambda a: a.priority)


# ─── 兜底（G-P2-6）──────────────────────────────────────────────────────────


def _fallback_actions(learner_state: dict) -> list[RecommendedAction]:
    """state 不全时：FSRS 到期 + 前沿新点；都没有则 PRACTICE。"""
    actions: list[RecommendedAction] = []
    due = learner_state.get("review_due", {}).get("due", 0)
    if due > 0:
        actions.append(RecommendedAction(
            action_type=ActionType.REVIEW_FLASHCARD,
            reason=f"（兜底）{due} 张到期闪卡，建议复习",
            params={"due_count": due},
            priority=1,
        ))
    frontier = learner_state.get("knowledge_graph", {}).get("frontier", [])
    if frontier:
        t = frontier[0]
        actions.append(RecommendedAction(
            action_type=ActionType.EXPLORE_FRONTIER,
            reason=f"（兜底）学习前沿知识点「{t.get('name', '')}」",
            params={"kp_id": t.get("id", ""), "kp_name": t.get("name", "")},
            priority=3,
        ))
    if not actions:
        actions.append(RecommendedAction(
            action_type=ActionType.PRACTICE,
            reason="（兜底）开始一组练习",
            params={},
            priority=4,
        ))
    return actions


# ─── 难度选择（G-P2-2）──────────────────────────────────────────────────────


def select_difficulty(correct_rate: float | None, *, current_tier: str = "blue") -> dict:
    """答对率硬规则难度调整（G-P2-2）。

    Returns {"tier": str, "should_fallback_to_prereq": bool}
    - correct_rate > 0.9  → 升一档
    - correct_rate < 0.8  → 降一档；已在 blue → should_fallback_to_prereq=True
    - 0.8–0.9 或 None     → 不变
    """
    if correct_rate is None:
        return {"tier": current_tier, "should_fallback_to_prereq": False}
    idx = _DIFFICULTY_TIERS.index(current_tier) if current_tier in _DIFFICULTY_TIERS else 0
    if correct_rate > 0.9:
        return {"tier": _DIFFICULTY_TIERS[min(idx + 1, len(_DIFFICULTY_TIERS) - 1)],
                "should_fallback_to_prereq": False}
    if correct_rate < 0.8:
        if idx == 0:
            return {"tier": "blue", "should_fallback_to_prereq": True}
        return {"tier": _DIFFICULTY_TIERS[idx - 1], "should_fallback_to_prereq": False}
    return {"tier": current_tier, "should_fallback_to_prereq": False}


# ─── 提取优先规则（G-P2-3）──────────────────────────────────────────────────


def _apply_retrieval_preference(actions: list[RecommendedAction]) -> None:
    """同等情况 PRACTICE（做题/回忆）优先于 EXPAND（再读讲义）。就地修改。"""
    practice = next((a for a in actions if a.action_type == ActionType.PRACTICE), None)
    expand = next((a for a in actions if a.action_type == ActionType.EXPAND), None)
    if practice and expand and expand.priority < practice.priority:
        practice.priority, expand.priority = expand.priority, practice.priority


# ─── 工具适配器（G-P2-5）────────────────────────────────────────────────────


def action_to_tool_call(action: RecommendedAction) -> tuple[str, dict]:
    """把引擎动作映射到 (tool_name, args_dict)，供 agent_service 直接 dispatch。

    绕过 LLM 自由选工具——引擎决策，LLM 执行。
    """
    t = action.action_type
    if t == ActionType.REVIEW_FLASHCARD:
        # FSRS 复习走前端 /v1/flashcards/due；Agent 设为 remind 状态引导用户
        return ("set_agent_state", {"state": "remind", "context": "review_flashcard"})
    if t in (ActionType.FILL_PREREQUISITE, ActionType.EXPLORE_FRONTIER):
        kp_id = action.params.get("kp_id", "")
        kp_name = action.params.get("kp_name", "")
        return ("start_training", {
            "knowledge_point_ids": [kp_id] if kp_id else [],
            "difficulty_tiers": ["blue"],
            "question_count": 5,
            "note": kp_name,
        })
    if t == ActionType.PRACTICE:
        return ("start_training", {"question_count": 10, "difficulty_tiers": ["blue", "purple"]})
    # EXPAND fallback
    return ("get_full_context", {})
