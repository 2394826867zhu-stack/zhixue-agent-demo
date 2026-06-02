"""G-P3-5 · PFA 对照：同数据跑 BKT / PFA / Best-LR，决定是否换引擎。

为什么：P2/P3 现用 BKT 估掌握度。换不换更强的学生模型（PFA / DKT）必须**用数据说话**，
不能拍脑袋。本模块在同一份作答序列上跑三种学生模型的**在线预测**（只用历史、不看当前标签），
比较 log-loss / accuracy / AUC，出对照报告。

三种模型：
- **BKT**：贝叶斯知识追踪（现行引擎），用 measurement_service 的参数与更新。
- **PFA**（Performance Factors Analysis）：logistic(β0 + γ·历史成功数 + ρ·历史失败数)，
  按序列内累计成功/失败计数建模（全局技能版，便于跨题对照）。梯度下降拟合，纯 Python、确定性。
- **Best-LR / base rate**：预测全局答对率的最优常数（log-loss 下的最优常数即经验均值），作下界基线。

兜底（设计 §3.3 / P3 兜底）：数据不足或 PFA 未**明显**胜出 → 保持 BKT，不换引擎。
空样本安全 no-op。输入为作答序列列表：每个元素是某学生在某 KP 上按时间排序的 bool 列表。

真实数据来源（P4 接）：训练答题 / 探针回流。现可直接喂 eval 集或真实导出跑对照。
"""
from __future__ import annotations

import math

from app.services.measurement_service import (
    bkt_update, P_INIT, _BKT_P_SLIP, _BKT_P_GUESS,
)

# 给出"建议换 PFA"所需的最小数据量与 log-loss 相对优势阈值（保守，宁可不换）
_MIN_RESPONSES = 50
_SWITCH_REL_MARGIN = 0.02  # PFA 须比 BKT 的 log-loss 低 ≥2% 才建议考虑

_EPS = 1e-12


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _clamp01(p: float) -> float:
    return min(1.0 - _EPS, max(_EPS, p))


# ── 分类指标 ──────────────────────────────────────

def log_loss(pairs: list[tuple[float, bool]]) -> float | None:
    """二元交叉熵均值（越低越好）。空 → None。"""
    if not pairs:
        return None
    total = 0.0
    for p, y in pairs:
        p = _clamp01(p)
        total += -(math.log(p) if y else math.log(1.0 - p))
    return total / len(pairs)


def accuracy(pairs: list[tuple[float, bool]], threshold: float = 0.5) -> float | None:
    if not pairs:
        return None
    correct = sum(1 for p, y in pairs if (p >= threshold) == bool(y))
    return correct / len(pairs)


def auc(pairs: list[tuple[float, bool]]) -> float | None:
    """ROC-AUC（Mann-Whitney U，平均秩处理并列）。单一类别无法定义 → None。"""
    pos = [p for p, y in pairs if y]
    neg = [p for p, y in pairs if not y]
    if not pos or not neg:
        return None
    return _auc_mann_whitney(pos, neg)


def _auc_mann_whitney(pos: list[float], neg: list[float]) -> float:
    # 平均秩法，O(n log n)
    labeled = [(s, 1) for s in pos] + [(s, 0) for s in neg]
    labeled.sort(key=lambda x: x[0])
    n = len(labeled)
    rank_sum_pos = 0.0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and labeled[j + 1][0] == labeled[i][0]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            if labeled[k][1] == 1:
                rank_sum_pos += avg_rank
        i = j + 1
    n_pos, n_neg = len(pos), len(neg)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


# ── 在线预测器（无泄漏：每步只用历史） ───────────────

def bkt_predict_sequence(responses: list[bool]) -> list[float]:
    """对一条作答序列，逐步输出"看到该题前"的 P(答对) 预测。"""
    preds: list[float] = []
    p = P_INIT
    for y in responses:
        preds.append(p * (1 - _BKT_P_SLIP) + (1 - p) * _BKT_P_GUESS)
        p = bkt_update(p, bool(y))
    return preds


def pfa_predict_sequence(responses: list[bool], params: dict) -> list[float]:
    """PFA 在线预测：用序列内"历史成功/失败计数"。"""
    b0, g, r = params["beta0"], params["gamma"], params["rho"]
    s = f = 0
    preds: list[float] = []
    for y in responses:
        preds.append(_sigmoid(b0 + g * s + r * f))
        if y:
            s += 1
        else:
            f += 1
    return preds


def _pfa_features(sequences: list[list[bool]]) -> list[tuple[float, float, bool]]:
    """展开成 (历史成功数, 历史失败数, 标签) 训练样本（每步一个）。"""
    rows: list[tuple[float, float, bool]] = []
    for seq in sequences:
        s = f = 0
        for y in seq:
            rows.append((float(s), float(f), bool(y)))
            if y:
                s += 1
            else:
                f += 1
    return rows


def pfa_fit(sequences: list[list[bool]], *, lr: float = 0.05, iters: int = 400) -> dict:
    """梯度下降拟合 PFA 全局参数 {beta0, gamma, rho}。确定性（无随机初始化）。"""
    rows = _pfa_features(sequences)
    b0 = g = r = 0.0
    if not rows:
        return {"beta0": 0.0, "gamma": 0.0, "rho": 0.0}
    n = len(rows)
    for _ in range(iters):
        gb0 = gg = gr = 0.0
        for s, f, y in rows:
            pred = _sigmoid(b0 + g * s + r * f)
            err = pred - (1.0 if y else 0.0)
            gb0 += err
            gg += err * s
            gr += err * f
        b0 -= lr * gb0 / n
        g -= lr * gg / n
        r -= lr * gr / n
    return {"beta0": b0, "gamma": g, "rho": r}


# ── 对照报告 ──────────────────────────────────────

def _metrics(pairs: list[tuple[float, bool]]) -> dict:
    return {"log_loss": log_loss(pairs), "accuracy": accuracy(pairs), "auc": auc(pairs)}


def engine_comparison_report(sequences: list[list[bool]]) -> dict:
    """同数据跑三模型，出对照报告 + 换引擎建议（保守兜底保持 BKT）。"""
    flat = [y for seq in sequences for y in seq]
    n = len(flat)
    base = {"n_sequences": len(sequences), "n_responses": n}

    if n < _MIN_RESPONSES:
        base.update({
            "models": {},
            "best_by_log_loss": None,
            "pfa_params": None,
            "recommendation": "insufficient_data",
        })
        return base

    # 在线预测对（无泄漏）
    bkt_pairs: list[tuple[float, bool]] = []
    pfa_params = pfa_fit(sequences)
    pfa_pairs: list[tuple[float, bool]] = []
    for seq in sequences:
        for p, y in zip(bkt_predict_sequence(seq), seq):
            bkt_pairs.append((p, y))
        for p, y in zip(pfa_predict_sequence(seq, pfa_params), seq):
            pfa_pairs.append((p, y))

    # Best-LR / base rate：log-loss 下的最优常数 = 经验均值
    base_rate = sum(1 for y in flat if y) / n
    base_pairs = [(base_rate, y) for y in flat]

    models = {
        "bkt": _metrics(bkt_pairs),
        "pfa": _metrics(pfa_pairs),
        "base_rate": _metrics(base_pairs),
    }
    best = min(models, key=lambda m: models[m]["log_loss"])

    # 建议：仅当 PFA 比 BKT 的 log-loss 低 ≥ margin 才"考虑换"；否则保持 BKT
    bkt_ll = models["bkt"]["log_loss"]
    pfa_ll = models["pfa"]["log_loss"]
    if pfa_ll < bkt_ll * (1 - _SWITCH_REL_MARGIN):
        recommendation = "consider_pfa"
    else:
        recommendation = "keep_bkt"

    base.update({
        "models": models,
        "best_by_log_loss": best,
        "pfa_params": pfa_params,
        "recommendation": recommendation,
    })
    return base
