"""学习内核 · 学习增益与校准指标（纯函数）。

理论：知曜学习内核_理论地基.md M10（Hake 归一化增益 + 掌握度校准）。
"""
from __future__ import annotations


def normalized_gain(*, pre: float, post: float) -> float:
    """Hake 归一化增益 g = (post - pre) / (100 - pre)。pre>=100 → 0。"""
    denom = 100.0 - pre
    if denom <= 0:
        return 0.0
    return (post - pre) / denom


def mastery_gain_per_hour(*, delta_mastery: float, hours: float) -> float:
    """单位学习时间的掌握提升。hours<=0 → 0。"""
    if hours <= 0:
        return 0.0
    return delta_mastery / hours


def calibration_bins(pairs: list[tuple[float, bool]], n_bins: int = 10) -> list[dict]:
    """(预测掌握概率, 实际是否答对) 分箱，返回每箱 {pred_mean, actual_rate, n}。"""
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, correct in pairs:
        idx = min(n_bins - 1, max(0, int(p * n_bins)))
        buckets[idx].append((p, correct))
    out = []
    for b in buckets:
        if not b:
            continue
        preds = [p for p, _ in b]
        acts = [1.0 if c else 0.0 for _, c in b]
        out.append({
            "pred_mean": sum(preds) / len(preds),
            "actual_rate": sum(acts) / len(acts),
            "n": len(b),
        })
    return out


def expected_calibration_error(pairs: list[tuple[float, bool]], n_bins: int = 10) -> float:
    """ECE：各箱 |预测均值 − 实际正确率| 按样本数加权平均。0=完美校准。"""
    bins = calibration_bins(pairs, n_bins=n_bins)
    total = sum(b["n"] for b in bins)
    if total == 0:
        return 0.0
    return sum(b["n"] * abs(b["pred_mean"] - b["actual_rate"]) for b in bins) / total


# ── G-P3-2 增益预测校准（gain_policy 预测的 Δp 期望 vs 真实 Δp）──────────────
#
# 用途：验收 P3 增益函数"预测有没有用"。决策时记下 gain_policy.expected_mastery_delta
# 的预测 Δp，事后由探针/答题回流真实 Δp，配成 (predicted, actual) 对喂入下面三个
# 纯函数。真实数据管道在 P4 建（探针结果回流，设计§4.3 外部锚）；现为评估框架，
# 单测可验证算法本身，生产侧无真实样本时返回空报告（安全 no-op）。理论：M10。


def gain_prediction_mae(pairs: list[tuple[float, float]]) -> float:
    """(预测Δp, 实测Δp) 的平均绝对误差。越小越准。空 → 0。"""
    if not pairs:
        return 0.0
    return sum(abs(pred - act) for pred, act in pairs) / len(pairs)


def prediction_actual_correlation(pairs: list[tuple[float, float]]) -> float | None:
    """预测Δp 与 实测Δp 的 Pearson 相关系数 ∈ [−1,1]。

    >0 且显著 = 增益函数有预测力（预测高增益的动作，实测增益也高）→ 值得上引擎。
    样本 <2 或预测/实测任一零方差 → None（无相关可言，退回固定优先级，设计§3.3 兜底）。
    """
    n = len(pairs)
    if n < 2:
        return None
    xs = [p for p, _ in pairs]
    ys = [a for _, a in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def gain_calibration_report(pairs: list[tuple[float, float]]) -> dict:
    """增益预测校准报告：{n, mae, correlation}。

    供 G-P3-2 决定增益函数是否经得起上生产、G-P3-5 与 PFA/Best-LR 同口径对照、
    以及 10 倍仪表盘的"诚实预测力"展示。空样本 → correlation=None 安全 no-op。
    """
    return {
        "n": len(pairs),
        "mae": gain_prediction_mae(pairs),
        "correlation": prediction_actual_correlation(pairs),
    }
