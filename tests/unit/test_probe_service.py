import pytest
from datetime import datetime, timedelta, timezone
from app.services import probe_service


def test_is_retention_probe_due_at_r_threshold():
    now = datetime.now(timezone.utc)
    due_old = probe_service.is_retention_probe_due(
        stability=10.0, last_reviewed_at=now - timedelta(days=12), now=now, target_r=0.9
    )
    due_fresh = probe_service.is_retention_probe_due(
        stability=10.0, last_reviewed_at=now, now=now, target_r=0.9
    )
    assert due_old is True
    assert due_fresh is False


def test_is_retention_probe_due_none_last_review_false():
    assert probe_service.is_retention_probe_due(
        stability=10.0, last_reviewed_at=None, now=None, target_r=0.9
    ) is False
