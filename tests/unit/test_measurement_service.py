from datetime import datetime, timedelta, timezone

import pytest

import app.services.measurement_service as ms


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
