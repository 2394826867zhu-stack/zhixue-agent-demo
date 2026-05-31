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
