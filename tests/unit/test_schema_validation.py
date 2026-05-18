from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.exam import ExamUpdate
from app.schemas.task import DailyTaskUpdate, PomodoroCreate


def test_daily_task_update_rejects_invalid_values():
    with pytest.raises(ValidationError):
        DailyTaskUpdate(title="   ")
    with pytest.raises(ValidationError):
        DailyTaskUpdate(estimated_minutes=0)
    with pytest.raises(ValidationError):
        DailyTaskUpdate(sort_order=-1)


def test_pomodoro_rejects_completed_before_started():
    with pytest.raises(ValidationError):
        PomodoroCreate(
            duration_minutes=25,
            started_at=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
            completed_at=datetime(2026, 5, 18, 9, 30, tzinfo=timezone.utc),
        )


def test_exam_update_rejects_empty_name():
    with pytest.raises(ValidationError):
        ExamUpdate(name="   ")
