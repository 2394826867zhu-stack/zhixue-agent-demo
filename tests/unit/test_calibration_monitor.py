from app.tasks import learning_kernel_tasks as lkt


def test_assess_calibration_flags_miscalibration():
    pairs = [(0.9, False), (0.95, False), (0.85, False)]  # 预测高、实际全错
    ece = lkt.assess_calibration(pairs, threshold=0.2)
    assert ece > 0.2


def test_assess_calibration_ok_when_calibrated():
    pairs = [(0.9, True), (0.1, False), (0.8, True), (0.2, False)]
    ece = lkt.assess_calibration(pairs, threshold=0.2)
    assert ece <= 0.2
