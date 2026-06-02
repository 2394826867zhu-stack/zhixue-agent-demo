"""G-P4-4 · 10 倍/效率仪表盘（对外可证，诚实优先）。

理论地基 M1 的诚实铁律落地：
- **产出效应**按 +1σ（约 50→84 百分位，ITS 工程靶子 d≈0.76）表述，**不喊 10 倍产出**；
- **"10 倍"仅用于效率维度**——省掉重读 / 遗忘 / 学错方向三大浪费；
- 效率省时的**具体倍数须真实 pre/post + 外部锚数据支撑**，未达标前不对外宣称数字（不自欺）。

本模块是纯函数装配器：把上层算好的真实信号汇成结构化诚实报告。空样本安全（增益=None），
但诚实框架表述始终在场。增益用 learning_gain 的 Hake 归一化增益 / 单位时长掌握增益，
基线取 BKT 先验 P_INIT（文档化近似；真实考前快照后续可替换）。
"""
from __future__ import annotations

from app.eval import learning_gain as lg
from app.services.measurement_service import P_INIT

_BASELINE_PCT = P_INIT * 100  # BKT 先验作"学前"基线（文档化近似）

# 诚实框架（固定表述，不依赖数据；有文献背书）
_HONEST_CEILING = "+1σ（约 50→84 百分位）"
_OUTPUT_FRAMING = "把一对一辅导的效果用 AI 规模化交付（ITS 工程靶子 d≈0.76，VanLehn）"
_EFFICIENCY_SCOPE = "「10 倍」仅用于效率维度：省掉重读 / 遗忘 / 学错方向三大浪费，不喊 10 倍产出"
_HONESTY_NOTE = (
    "产出效应上限按 +1σ 诚实表述；效率维度的省时倍数须由真实 pre/post 增益 + 外部成绩锚"
    "共同支撑，未达标前不对外宣称具体倍数。"
)


def efficiency_dashboard(
    *,
    avg_mastery_pct: float | None,
    probed_kp_count: int,
    focus_minutes: int,
    anchor: dict,
) -> dict:
    """汇总诚实仪表盘。anchor 为 score_anchor.anchor_report 结果（外部锚验证不自欺）。"""
    # 产出：Hake 归一化增益（基线=P_INIT），无掌握数据 → None
    norm_gain: float | None = None
    gain_per_hour: float | None = None
    if avg_mastery_pct is not None and probed_kp_count > 0:
        norm_gain = lg.normalized_gain(pre=_BASELINE_PCT, post=avg_mastery_pct)
        if focus_minutes > 0:
            gain_per_hour = lg.mastery_gain_per_hour(
                delta_mastery=avg_mastery_pct / 100.0 - P_INIT,
                hours=focus_minutes / 60.0,
            )

    return {
        "output_effect": {
            "honest_ceiling": _HONEST_CEILING,
            "framing": _OUTPUT_FRAMING,
            "normalized_gain": norm_gain,          # Hake ⟨g⟩，基线=P_INIT
            "baseline_pct": _BASELINE_PCT,
            "avg_mastery_pct": avg_mastery_pct,
            "probed_kp_count": probed_kp_count,
        },
        "efficiency": {
            "claim_scope": _EFFICIENCY_SCOPE,
            "focus_minutes": focus_minutes,
            "mastery_gain_per_hour": gain_per_hour,  # 单位时长掌握增益（真实可测）
        },
        "external_anchor": anchor,                  # 复用 G-P4-2，验证度量不自欺
        "honesty_note": _HONESTY_NOTE,
    }
