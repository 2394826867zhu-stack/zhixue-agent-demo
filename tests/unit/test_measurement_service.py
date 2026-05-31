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
