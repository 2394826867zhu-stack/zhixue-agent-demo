def test_subscription_event_model_importable():
    from app.models.subscription_event import SubscriptionEvent
    assert SubscriptionEvent.__tablename__ == "subscription_events"


from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from app.services.subscription_service import is_pro, get_status, verify_webhook_auth


def _user(plan_type: str, expires_at=None, trial_used: bool = False, trial_ends_at=None) -> MagicMock:
    u = MagicMock()
    u.plan_type = plan_type
    u.plan_expires_at = expires_at
    # E-04 · 镜像真实 User 的试用字段（默认未用过试用、无试用到期）
    u.trial_used = trial_used
    u.trial_ends_at = trial_ends_at
    return u


def test_free_user_not_pro():
    assert is_pro(_user("free")) is False


def test_pro_user_no_expiry_is_pro():
    assert is_pro(_user("pro", None)) is True


def test_pro_user_future_expiry_is_pro():
    future = datetime.now(timezone.utc) + timedelta(days=30)
    assert is_pro(_user("pro", future)) is True


def test_pro_user_past_expiry_not_pro():
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert is_pro(_user("pro", past)) is False


def test_edu_user_is_pro():
    assert is_pro(_user("edu")) is True


def test_verify_webhook_auth_valid():
    assert verify_webhook_auth("Bearer secret123", "secret123") is True


def test_verify_webhook_auth_wrong_secret():
    assert verify_webhook_auth("Bearer wrong", "secret123") is False


def test_verify_webhook_auth_missing_header():
    assert verify_webhook_auth(None, "secret123") is False


def test_verify_webhook_auth_malformed():
    assert verify_webhook_auth("Basic secret123", "secret123") is False


def test_get_status_free_user():
    user = _user("free")
    status = get_status(user)
    assert status["plan_type"] == "free"
    assert status["is_pro"] is False
    assert status["plan_expires_at"] is None
    assert status["days_remaining"] is None
    assert status["features"]["advanced_reports"] is False
    assert status["features"]["knowledge_base_upload"] is False


def test_get_status_pro_user_with_expiry():
    future = datetime.now(timezone.utc) + timedelta(days=15, seconds=1)
    user = _user("pro", future)
    status = get_status(user)
    assert status["plan_type"] == "pro"
    assert status["is_pro"] is True
    assert status["days_remaining"] == 15
    assert status["features"]["advanced_reports"] is True
    assert status["features"]["knowledge_base_upload"] is True


import pytest
from unittest.mock import patch
from app.core.exceptions import SubscriptionRequiredError


def test_subscription_required_error_has_code_4031():
    err = SubscriptionRequiredError()
    assert err.code == 4031
    assert err.status_http == 403


@pytest.mark.asyncio
async def test_require_pro_raises_for_free_user():
    from app.api.deps import require_pro
    free_user = _user("free")
    with pytest.raises(SubscriptionRequiredError):
        await require_pro(user=free_user)


@pytest.mark.asyncio
async def test_require_pro_raises_for_expired_pro_user():
    from app.api.deps import require_pro
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_user = _user("pro", past)
    with pytest.raises(SubscriptionRequiredError):
        await require_pro(user=expired_user)


@pytest.mark.asyncio
async def test_require_pro_passes_for_pro_user():
    from app.api.deps import require_pro
    future = datetime.now(timezone.utc) + timedelta(days=10)
    pro_user = _user("pro", future)
    result = await require_pro(user=pro_user)
    assert result is pro_user
