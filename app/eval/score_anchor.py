"""G-P4-2 · 外部成绩锚：内部掌握概率 vs 真实考试分的相关分析。

理论地基 M10 外部锚——周期性把内部掌握概率与真实考试分做相关，验证度量不自欺。
纯函数；空样本 / n<2 / 零方差 → correlation=None 安全 no-op。
复用 learning_gain 的 Pearson（与增益校准同口径）。
"""
from __future__ import annotations

from app.eval.learning_gain import prediction_actual_correlation


def anchor_report(pairs: list[tuple[float, float]]) -> dict:
    """pairs: list[(score_pct 0-100, mastery_pct 同一学科同一时点)]。

    返回 {n, correlation, mean_score_pct, mean_mastery_pct}。
    correlation 为 Pearson（对称），n<2 或任一列零方差 → None（无相关可言，不自欺）。
    """
    n = len(pairs)
    if n == 0:
        return {"n": 0, "correlation": None, "mean_score_pct": None, "mean_mastery_pct": None}
    return {
        "n": n,
        "correlation": prediction_actual_correlation(pairs),
        "mean_score_pct": sum(s for s, _ in pairs) / n,
        "mean_mastery_pct": sum(m for _, m in pairs) / n,
    }
