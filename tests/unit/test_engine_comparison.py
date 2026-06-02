"""G-P3-5 · PFA 对照引擎评估 — 单测（TDD 先行）。

同数据跑 BKT / PFA / Best-LR(base rate)，比较预测力，出对照报告决定是否换引擎。
纯函数 + 空样本安全 no-op（设计 P3 兜底：未经数据证明则保持现有 BKT/P2）。
"""
import math
import pytest

from app.eval import engine_comparison as ec


# ── 指标助手 ──────────────────────────────────────

def test_log_loss_perfect_is_zero():
    # 预测与标签完全一致（钳制后接近 0）
    ll = ec.log_loss([(0.999, True), (0.001, False)])
    assert ll < 0.05


def test_log_loss_worse_than_base():
    confident_wrong = ec.log_loss([(0.001, True), (0.999, False)])
    base = ec.log_loss([(0.5, True), (0.5, False)])
    assert confident_wrong > base


def test_accuracy_threshold():
    assert ec.accuracy([(0.9, True), (0.2, False), (0.6, False)]) == pytest.approx(2 / 3)


def test_auc_perfect_and_random():
    # 完美排序 AUC=1
    assert ec.auc([(0.9, True), (0.8, True), (0.2, False), (0.1, False)]) == pytest.approx(1.0)
    # 单类别无法定义 → None
    assert ec.auc([(0.9, True), (0.8, True)]) is None


# ── 在线预测无泄漏 ────────────────────────────────

def test_bkt_first_prediction_uses_prior():
    # 首个观测的预测只依赖先验 P_INIT，不看标签
    preds = ec.bkt_predict_sequence([True, True, True])
    from app.services.measurement_service import P_INIT, _BKT_P_SLIP, _BKT_P_GUESS
    expected_first = P_INIT * (1 - _BKT_P_SLIP) + (1 - P_INIT) * _BKT_P_GUESS
    assert preds[0] == pytest.approx(expected_first, abs=1e-9)
    assert len(preds) == 3
    # 连续答对 → 预测概率单调上升
    assert preds[1] > preds[0] and preds[2] > preds[1]


def test_pfa_predict_sequence_length_and_range():
    params = {"beta0": 0.0, "gamma": 0.4, "rho": -0.1}
    preds = ec.pfa_predict_sequence([True, False, True], params)
    assert len(preds) == 3
    assert all(0.0 <= p <= 1.0 for p in preds)


# ── 拟合 + 报告 ───────────────────────────────────

def _learning_dataset(n_students=40, length=8):
    """合成"练习中逐步学会"数据：随练习次数答对率上升（PFA 该能学到 gamma>0）。"""
    seqs = []
    for s in range(n_students):
        seq = []
        for i in range(length):
            # 第 i 次正确概率随 i 上升
            p = 0.2 + 0.7 * (i / (length - 1))
            # 用确定性伪随机（按 s,i 派生）避免依赖 random
            r = ((s * 31 + i * 17) % 100) / 100.0
            seq.append(r < p)
        seqs.append(seq)
    return seqs


def test_pfa_fit_learns_positive_gamma_on_learning_data():
    params = ec.pfa_fit(_learning_dataset())
    # 成功次数越多越可能答对 → gamma 应为正
    assert params["gamma"] > 0


def test_report_empty_is_safe_noop():
    rep = ec.engine_comparison_report([])
    assert rep["n_responses"] == 0
    assert rep["best_by_log_loss"] is None
    assert rep["recommendation"] == "insufficient_data"


def test_report_insufficient_data_keeps_bkt():
    rep = ec.engine_comparison_report([[True, False]])  # 太少
    assert rep["recommendation"] == "insufficient_data"


def test_report_wellformed_on_learning_data():
    rep = ec.engine_comparison_report(_learning_dataset())
    assert rep["n_responses"] > 0
    for m in ("bkt", "pfa", "base_rate"):
        assert m in rep["models"]
        assert rep["models"][m]["log_loss"] is not None
    assert rep["best_by_log_loss"] in ("bkt", "pfa", "base_rate")
    # 默认兜底：除非 PFA 明显更优，否则保持 BKT
    assert rep["recommendation"] in ("keep_bkt", "consider_pfa")
    # 学习型数据上，PFA/BKT 都应优于常数基线
    assert rep["models"]["base_rate"]["log_loss"] >= min(
        rep["models"]["bkt"]["log_loss"], rep["models"]["pfa"]["log_loss"]
    ) - 1e-9
