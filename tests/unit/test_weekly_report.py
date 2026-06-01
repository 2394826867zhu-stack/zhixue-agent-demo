"""Unit tests for D-11 weekly report pure helper functions.

No DB / LLM mocking required — these functions are pure.
"""
import pytest
from app.services.reports_service import classify_p_mastery, build_mastery_distribution
from app.schemas.reports import MasteryDistribution


def test_classify_struggling():
    assert classify_p_mastery(0.1) == "struggling"


def test_classify_learning():
    assert classify_p_mastery(0.5) == "learning"


def test_classify_mastered():
    assert classify_p_mastery(0.9) == "mastered"


def test_classify_unprobed():
    assert classify_p_mastery(None) == "unprobed"


def test_classify_boundary_0_3():
    # boundary: 0.3 is "learning"
    assert classify_p_mastery(0.3) == "learning"


def test_classify_boundary_0_7():
    # boundary: 0.7 is "learning"
    assert classify_p_mastery(0.7) == "learning"


def test_build_mastery_distribution_mixed():
    dist, avg = build_mastery_distribution([0.1, 0.5, 0.9, None])
    assert dist.struggling == 1
    assert dist.learning == 1
    assert dist.mastered == 1
    assert dist.unprobed == 1
    assert avg == pytest.approx(0.5, abs=0.01)  # (0.1 + 0.5 + 0.9) / 3


def test_build_mastery_distribution_all_unprobed():
    dist, avg = build_mastery_distribution([None, None])
    assert dist.unprobed == 2
    assert avg is None


def test_build_mastery_distribution_empty():
    dist, avg = build_mastery_distribution([])
    assert dist.struggling == 0
    assert dist.learning == 0
    assert dist.mastered == 0
    assert dist.unprobed == 0
    assert avg is None


def test_build_mastery_distribution_returns_mastery_distribution_type():
    dist, avg = build_mastery_distribution([0.2, 0.6])
    assert isinstance(dist, MasteryDistribution)


def test_classify_zero_is_struggling():
    assert classify_p_mastery(0.0) == "struggling"


def test_classify_one_is_mastered():
    assert classify_p_mastery(1.0) == "mastered"
