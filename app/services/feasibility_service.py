"""项目可行性估算（v3 · INC-D）。

设计：docs/superpowers/specs/2026-06-25-project-creation-system-v3-design.md §5.4
预估耗时 vs 可用时数 → 比值 / 档位 / 建议（**soft warning，不拦截**）。两处用：
① 生成前粗估 → feasibility_advice 注入 F1 prompt 调深度（INC-C 的 feasibility_advice 参数）；
② 生成后用真节点数回填 → 确认页展示（INC-E preview，D7）。

纯逻辑，无 DB / 无 IO。
"""
from __future__ import annotations

from datetime import datetime, timezone

# 每难度档每节点平均学习时数（spec §5.4：蓝 0.5h / 紫 1h / 金 2h）
_HOURS_PER_DIFF = {"blue": 0.5, "purple": 1.0, "gold": 2.0}
# goal_type → 默认掌握深度（与 framework_service.GOAL_DEFAULT_DEPTH 对齐）
_GOAL_DEFAULT_DEPTH = {"exam": "deep", "skill": "working", "interest": "surface", "remedial": "deep"}
# 深度 → 粗估每节点平均时长（无逐节点难度时）
_DEPTH_AVG_HOURS = {"surface": 0.6, "working": 1.0, "deep": 1.3}

# 档位（英文枚举给前端 switch 配色；label 中文展示）
_BAND_LABEL = {"ample": "时间充裕", "fit": "时间合适", "tight": "时间偏紧",
               "infeasible": "时间不足", "unknown": "未设时间"}
# 用户可读建议（确认页，无 optional/importance 术语）
_USER_ADVICE = {
    "ample": "时间充裕，框架可以排得更扎实一些。",
    "fit": "",
    "tight": "时间偏紧，建议缩小学习范围或增加每周投入。",
    "infeasible": "按当前时间很难学完，建议改用「自选专题」缩小范围，或调整目标日期。",
    "unknown": "",
}
# 注入 F1 prompt 的 LLM 指令（None=不注入）
_PROMPT_ADVICE = {
    "ample": "时间充裕，可以适当增加深度节点和挑战性内容。",
    "fit": None,
    "tight": "时间紧张，请优先核心节点，把非必要的课时标为 optional:true。",
    "infeasible": "时间严重不足，请大幅精简：只保留最核心的主干课时，非必要一律标 optional:true。",
    "unknown": None,
}


def estimate_node_count(goal_type: str, scope_mode: str, mastery_depth: str | None) -> int:
    """生成前粗估节点数（按 scope × goal_type × 深度），钳到 8-30（与 F1 规模约束一致）。"""
    base = {"full_subject": 24, "selected_topics": 16, "prerequisites_only": 12}.get(scope_mode, 24)
    if goal_type == "exam":
        base = int(base * 1.1)
    elif goal_type == "interest":
        base = int(base * 0.8)
    depth = mastery_depth or _GOAL_DEFAULT_DEPTH.get(goal_type, "working")
    base = int(base * {"surface": 0.85, "working": 1.0, "deep": 1.15}.get(depth, 1.0))
    return max(8, min(base, 30))


def estimate_hours_rough(node_count: int, mastery_depth: str | None) -> float:
    """粗估总耗时（无逐节点难度时，按深度给平均每节点时长）。"""
    avg = _DEPTH_AVG_HOURS.get(mastery_depth or "working", 1.0)
    return node_count * avg


def estimate_hours_from_counts(blue: int, purple: int, gold: int) -> float:
    """生成后按真节点难度分布算总耗时（INC-E 回填用）。"""
    return (blue * _HOURS_PER_DIFF["blue"] + purple * _HOURS_PER_DIFF["purple"]
            + gold * _HOURS_PER_DIFF["gold"])


def remaining_weeks(target_completion_date: datetime | None, default: float = 12.0) -> float:
    """从现在到目标日期的剩余周数；无日期 → default。"""
    if not target_completion_date:
        return float(default)
    now = datetime.now(timezone.utc)
    tcd = target_completion_date
    if tcd.tzinfo is None:
        tcd = tcd.replace(tzinfo=timezone.utc)
    return max(1.0, (tcd - now).days / 7.0)


def feasibility_band(ratio: float) -> str:
    if ratio <= 0.8:
        return "ample"
    if ratio <= 1.2:
        return "fit"
    if ratio <= 2.0:
        return "tight"
    return "infeasible"


def estimate_feasibility(*, estimated_hours: float, weekly_hours: float | None,
                         remaining_weeks_val: float) -> dict:
    """→ {ratio, band, label, available_hours, estimated_hours, advice}。
    无 weekly_hours → band=unknown（不拦截、不注入）。"""
    est = round(estimated_hours, 1)
    if not weekly_hours or weekly_hours <= 0:
        return {"ratio": None, "band": "unknown", "label": _BAND_LABEL["unknown"],
                "available_hours": None, "estimated_hours": est, "advice": ""}
    available = weekly_hours * remaining_weeks_val
    ratio = estimated_hours / available if available > 0 else float("inf")
    band = feasibility_band(ratio)
    return {
        "ratio": round(ratio, 2),
        "band": band,
        "label": _BAND_LABEL[band],
        "available_hours": round(available, 1),
        "estimated_hours": est,
        "advice": _USER_ADVICE[band],
    }


def feasibility_advice_for_prompt(band: str) -> str | None:
    """生成前注入 F1 prompt 的片段（None=不注入，正常生成）。"""
    return _PROMPT_ADVICE.get(band)
