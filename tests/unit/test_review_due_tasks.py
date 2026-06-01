from app.tasks.review_due_tasks import should_send_review_reminder


def test_sends_when_cards_due_and_pref_enabled():
    assert should_send_review_reminder(
        due_count=3,
        flashcard_reminder_enabled=True,
        hours_since_last_reminder=None,
    ) is True


def test_skips_when_pref_disabled():
    assert should_send_review_reminder(
        due_count=5,
        flashcard_reminder_enabled=False,
        hours_since_last_reminder=None,
    ) is False


def test_skips_when_no_due_cards():
    assert should_send_review_reminder(
        due_count=0,
        flashcard_reminder_enabled=True,
        hours_since_last_reminder=None,
    ) is False


def test_deduplicates_within_8h():
    assert should_send_review_reminder(
        due_count=5,
        flashcard_reminder_enabled=True,
        hours_since_last_reminder=4.0,
    ) is False


def test_allows_after_8h():
    assert should_send_review_reminder(
        due_count=5,
        flashcard_reminder_enabled=True,
        hours_since_last_reminder=9.0,
    ) is True


def test_review_message_singular():
    from app.tasks.review_due_tasks import review_due_message
    msg = review_due_message(1)
    assert "1" in msg


def test_review_message_plural():
    from app.tasks.review_due_tasks import review_due_message
    msg = review_due_message(12)
    assert "12" in msg
