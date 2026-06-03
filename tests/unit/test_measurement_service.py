from datetime import datetime, timedelta, timezone

import pytest

import app.services.measurement_service as ms


class _DummyKP:
    def __init__(self, p_mastery):
        self.p_mastery = p_mastery


def test_retrievability_one_at_zero_elapsed():
    now = datetime.now(timezone.utc)
    assert ms.retrievability(stability=10.0, last_reviewed_at=now, now=now) == pytest.approx(1.0, abs=1e-6)


def test_retrievability_about_0_9_at_one_stability():
    now = datetime.now(timezone.utc)
    r = ms.retrievability(stability=10.0, last_reviewed_at=now - timedelta(days=10), now=now)
    assert r == pytest.approx(0.9, abs=0.02)


def test_effective_mastery_decays_with_time():
    now = datetime.now(timezone.utc)
    fresh = ms.effective_mastery(p_mastery=0.8, stability=10.0, last_reviewed_at=now, now=now)
    later = ms.effective_mastery(p_mastery=0.8, stability=10.0, last_reviewed_at=now,
                                 now=now + timedelta(days=30))
    assert fresh == pytest.approx(0.8, abs=1e-3)
    assert later < fresh
    assert 0.0 <= later <= 1.0


def test_effective_mastery_none_degrades_gracefully():
    assert ms.effective_mastery(p_mastery=None, stability=10.0, last_reviewed_at=None, now=None) == 0.0
    assert ms.effective_mastery(p_mastery=0.7, stability=10.0, last_reviewed_at=None, now=None) == pytest.approx(0.7, abs=1e-6)


def test_bkt_update_correct_raises_belief():
    assert ms.bkt_update(0.3, True) > 0.3


def test_bkt_update_wrong_lowers_belief():
    # 答错后观测后验应低于先验（再叠加学习转移仍应明显下降）
    assert ms.bkt_update(0.8, False) < 0.8


def test_bkt_update_none_prior_uses_init():
    assert 0.0 < ms.bkt_update(None, True) <= 1.0


def test_bkt_update_stays_in_unit_interval():
    for prior in (0.0, 0.5, 1.0):
        for correct in (True, False):
            v = ms.bkt_update(prior, correct)
            assert 0.0 <= v <= 1.0


def test_bkt_no_absorbing_state_at_p1():
    # 审计 L2-001：p=1.0 时 (1-p)=0 曾使答错的贝叶斯后验恒 1.0（吸收态——该 KP 永远免疫
    # "答错降掌握度"，违反 BKT 单调性）。修复后必须：
    # ① 历史已存 1.0 数据传入答错，严格低于 1.0（能下降）
    assert ms.bkt_update(1.0, False) < 1.0
    # ② 连对 100 次也不会收敛到 1.0（上限钳 <1.0，保证 (1-p)>0）
    p = None
    for _ in range(100):
        p = ms.bkt_update(p, True)
    assert p < 1.0
    # ③ 收敛到上限后，一次答错必须严格降低掌握度
    assert ms.bkt_update(p, False) < p


def test_bkt_guess_slip_clamped_against_degeneracy():
    # M2 防退化安全不变量（审计 A-2）：传入退化参数 guess=slip=0.9（>0.5）必须被钳到 0.5，
    # 钳制后"答对"的后验信念不得低于"答错"——否则模型会把答错判为更掌握。
    after_wrong = ms.bkt_update(0.5, False, guess=0.9, slip=0.9)
    after_right = ms.bkt_update(0.5, True, guess=0.9, slip=0.9)
    assert after_right >= after_wrong


def test_apply_answer_to_kp_updates_in_place():
    kp = _DummyKP(p_mastery=0.3)
    ms.apply_answer_to_kp(kp, correct=True)
    assert kp.p_mastery > 0.3


def test_apply_answer_to_kp_handles_none_prior():
    kp = _DummyKP(p_mastery=None)
    ms.apply_answer_to_kp(kp, correct=True)
    assert kp.p_mastery is not None


def test_new_columns_exist_on_models():
    # P0-1 storage groundwork: calibrated mastery + probe flags (migration 037)
    from app.models.knowledge_point import KnowledgePoint
    from app.models.training import TrainingQuestion

    assert hasattr(KnowledgePoint, "p_mastery")
    assert hasattr(KnowledgePoint, "last_probe")
    assert hasattr(TrainingQuestion, "is_probe")
    assert hasattr(TrainingQuestion, "probe_kind")
