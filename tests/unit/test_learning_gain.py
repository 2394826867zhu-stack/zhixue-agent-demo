import pytest

from app.eval import learning_gain as lg


def test_normalized_gain_hake():
    assert lg.normalized_gain(pre=40.0, post=70.0) == pytest.approx(0.5, abs=1e-6)
    assert lg.normalized_gain(pre=100.0, post=100.0) == 0.0


def test_mastery_gain_per_hour():
    assert lg.mastery_gain_per_hour(delta_mastery=0.3, hours=1.5) == pytest.approx(0.2, abs=1e-6)
    assert lg.mastery_gain_per_hour(delta_mastery=0.3, hours=0.0) == 0.0


def test_calibration_bins_groups_pred_vs_actual():
    pairs = [(0.9, True), (0.85, True), (0.1, False), (0.15, False)]
    bins = lg.calibration_bins(pairs, n_bins=2)
    high = [b for b in bins if b["pred_mean"] > 0.5][0]
    low = [b for b in bins if b["pred_mean"] <= 0.5][0]
    assert high["actual_rate"] == pytest.approx(1.0)
    assert low["actual_rate"] == pytest.approx(0.0)


def test_expected_calibration_error_well_calibrated_low():
    # 预测概率与实际命中率一致 → ECE 低；严重失准（预测高却全错）→ ECE 高
    calibrated = [(1.0, True), (1.0, True), (0.0, False), (0.0, False)]
    miscalibrated = [(0.95, False), (0.9, False), (0.92, False)]
    assert lg.expected_calibration_error(calibrated, n_bins=10) == pytest.approx(0.0, abs=1e-6)
    assert lg.expected_calibration_error(miscalibrated, n_bins=10) > 0.5
