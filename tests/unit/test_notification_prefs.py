import pytest
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
