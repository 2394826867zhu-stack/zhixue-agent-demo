import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError
from app.schemas.user_prefs import UserPrefsOut, UserPrefsUpdate


def test_prefs_out_includes_notification_fields():
    out = UserPrefsOut(
        theme_mode="auto",
        dynamic_type_scale=1.0,
        reduced_motion=False,
        haptics_enabled=True,
        voice_enabled=False,
        push_enabled=True,
        flashcard_reminder_enabled=True,
        daily_reminder_enabled=False,
        daily_reminder_time=None,
    )
    assert out.push_enabled is True
    assert out.flashcard_reminder_enabled is True
    assert out.daily_reminder_enabled is False
    assert out.daily_reminder_time is None


def test_prefs_update_daily_reminder_time_format():
    # valid
    u = UserPrefsUpdate(daily_reminder_time="20:00")
    assert u.daily_reminder_time == "20:00"
    # invalid format
    with pytest.raises(ValidationError):
        UserPrefsUpdate(daily_reminder_time="8pm")
    # null is ok
    u2 = UserPrefsUpdate(daily_reminder_time=None)
    assert u2.daily_reminder_time is None


@pytest.mark.asyncio
async def test_push_skipped_when_push_disabled(monkeypatch):
    """notification_service.create() must NOT call push_service when push_enabled=False."""
    from app.services import notification_service

    # Build a fake DB session that returns a user with push_enabled=False
    fake_user = MagicMock()
    fake_user.id = __import__("uuid").uuid4()
    fake_user.expo_push_token = "ExponentPushToken[xxx]"
    fake_user.push_enabled = False

    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = fake_user

    fake_db = MagicMock()
    fake_db.add = MagicMock()
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    fake_db.execute = AsyncMock(return_value=fake_result)
    fake_db.get = AsyncMock(return_value=None)

    push_called = []

    async def fake_send(token, body):
        push_called.append(token)
        return None

    monkeypatch.setattr("app.services.notification_service._push_svc.send_push", fake_send)

    svc = notification_service.NotificationService()
    await svc.create(fake_db, str(fake_user.id), "测试", "test_type", force_push=True)

    assert push_called == [], "push should NOT be called when push_enabled=False"
