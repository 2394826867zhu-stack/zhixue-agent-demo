from app.tasks.checkin_reminder_tasks import should_send_checkin_reminder


def test_sends_at_correct_hour():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="20:00",
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=None,
    ) is True


def test_skips_wrong_hour():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="20:00",
        current_bj_hour=21,
        checked_in_today=False,
        hours_since_last_reminder=None,
    ) is False


def test_skips_if_already_checked_in():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="20:00",
        current_bj_hour=20,
        checked_in_today=True,
        hours_since_last_reminder=None,
    ) is False


def test_skips_when_disabled():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=False,
        daily_reminder_time="20:00",
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=None,
    ) is False


def test_skips_when_no_time_set():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time=None,
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=None,
    ) is False


def test_deduplicates_within_23h():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="20:00",
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=5.0,
    ) is False


def test_allows_after_23h():
    assert should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="20:00",
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=24.0,
    ) is True


def test_handles_invalid_time_format():
    result = should_send_checkin_reminder(
        daily_reminder_enabled=True,
        daily_reminder_time="8pm",  # malformed
        current_bj_hour=20,
        checked_in_today=False,
        hours_since_last_reminder=None,
    )
    assert result is False
