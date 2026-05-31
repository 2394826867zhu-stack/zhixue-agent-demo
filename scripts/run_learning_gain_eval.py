"""学习增益基线脚本（手动跑）：
   PYTHONPATH=. python scripts/run_learning_gain_eval.py
构造合成答题序列，跑 BKT，输出 ①平均归一化增益 ②单位时长掌握增益 ③校准 ECE + 分箱。
纯 BKT 逻辑无需 DB（P0 建立可复现基线；P4 换真实 KP 序列时再接 zhiyao_test）。
"""
from app.eval import learning_gain as lg
from app.services import measurement_service as ms

SYNTH = [
    {"answers": [False, True, True, True], "hours": 0.5},
    {"answers": [False, False, True, False], "hours": 0.5},
    {"answers": [True, True, True, True], "hours": 0.3},
]


def _run_sequence(answers):
    p = None
    pairs = []
    pre = ms.P_INIT
    for correct in answers:
        pred = ms.P_INIT if p is None else p
        pairs.append((pred, correct))
        p = ms.bkt_update(prior=p, correct=correct)
    post = p if p is not None else pre
    return pre, post, pairs


def main():
    all_pairs, n_gains, n_rates = [], [], []
    for s in SYNTH:
        pre, post, pairs = _run_sequence(s["answers"])
        all_pairs.extend(pairs)
        n_gains.append(lg.normalized_gain(pre=pre * 100, post=post * 100))
        n_rates.append(lg.mastery_gain_per_hour(delta_mastery=post - pre, hours=s["hours"]))
    print("== 学习增益基线 ==")
    print(f"平均归一化增益 <g> = {sum(n_gains) / len(n_gains):.3f}")
    print(f"平均单位时长掌握增益 = {sum(n_rates) / len(n_rates):.3f} /h")
    print(f"校准 ECE = {lg.expected_calibration_error(all_pairs, n_bins=5):.3f}")
    for b in lg.calibration_bins(all_pairs, n_bins=5):
        print(f"  bin pred={b['pred_mean']:.2f} actual={b['actual_rate']:.2f} n={b['n']}")


if __name__ == "__main__":
    main()
