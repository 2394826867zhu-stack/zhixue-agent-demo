# Push Notifications Pipeline (C-17 ~ C-21) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, preference-respecting push notification pipeline: store per-user notification preferences, extract a testable push service, add an FSRS-driven hourly review reminder task, and add a user-scheduled daily checkin reminder task.

**Architecture:** Three layers — (1) User notification preferences stored in DB and surfaced via existing `PATCH /profile/prefs`; (2) `push_service.py` handles Expo HTTP calls and auto-clears stale device tokens; (3) two new Celery beat tasks scan FSRS state and user schedules hourly to fire targeted pushes. All decisions are gated by per-user preference flags so users can opt out of any push type.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery beat, httpx, Expo Push API (`https://exp.host/--/api/v2/push/send`), pytest + monkeypatch

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `alembic/versions/039_notification_prefs.py` | Migration: 4 new columns on `users` |
| Modify | `app/models/user.py` | Add 4 pref fields |
| Modify | `app/schemas/user_prefs.py` | Extend `UserPrefsOut` + `UserPrefsUpdate` |
| Modify | `app/api/v1/user_prefs.py` | Read/write new fields |
| Create | `app/services/push_service.py` | Expo push + DeviceNotRegistered cleanup |
| Modify | `app/services/notification_service.py` | Use push_service; gate on `push_enabled` |
| Create | `app/tasks/review_due_tasks.py` | FSRS due today → push (C-17/C-19) |
| Create | `app/tasks/checkin_reminder_tasks.py` | Daily checkin at user-chosen time (C-20) |
| Modify | `app/tasks/celery_app.py` | Register 2 new beat schedules |
| Create | `tests/unit/test_notification_prefs.py` | Prefs schema + push gate |
| Create | `tests/unit/test_push_service.py` | Expo HTTP mock |
| Create | `tests/unit/test_review_due_tasks.py` | Pure-function guard logic |
| Create | `tests/unit/test_checkin_reminder_tasks.py` | Pure-function guard logic |

---

## Task 1: Notification Preferences (C-21) — migration + model + API

**Files:**
- Create: `alembic/versions/039_notification_prefs.py`
- Modify: `app/models/user.py`
- Modify: `app/schemas/user_prefs.py`
- Modify: `app/api/v1/user_prefs.py`
- Create: `tests/unit/test_notification_prefs.py`

- [ ] **Step 1: Write the failing schema test**

```python
# tests/unit/test_notification_prefs.py
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
    assert out.daily_reminder_enabled is False
    assert out.daily_reminder_time is None


def test_prefs_update_daily_reminder_time_format():
    from pydantic import ValidationError
    import pytest
    # valid
    u = UserPrefsUpdate(daily_reminder_time="20:00")
    assert u.daily_reminder_time == "20:00"
    # invalid format
    with pytest.raises(ValidationError):
        UserPrefsUpdate(daily_reminder_time="8pm")
    # null is ok
    u2 = UserPrefsUpdate(daily_reminder_time=None)
    assert u2.daily_reminder_time is None
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/unit/test_notification_prefs.py -v
```
Expected: FAIL — `UserPrefsOut` doesn't accept `push_enabled`

- [ ] **Step 3: Add fields to `app/schemas/user_prefs.py`**

Replace the entire file content:

```python
"""用户偏好 Schemas — v2 PRD 9.11 + C-21 通知偏好"""
import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class UserPrefsOut(BaseModel):
    theme_mode: Literal["auto", "light", "dark"]
    dynamic_type_scale: float
    reduced_motion: bool
    haptics_enabled: bool
    voice_enabled: bool
    # C-21 通知偏好
    push_enabled: bool
    flashcard_reminder_enabled: bool
    daily_reminder_enabled: bool
    daily_reminder_time: str | None  # "HH:MM" e.g. "20:00"; None = not set


class UserPrefsUpdate(BaseModel):
    theme_mode: Literal["auto", "light", "dark"] | None = None
    dynamic_type_scale: float | None = Field(default=None, ge=0.8, le=1.4)
    reduced_motion: bool | None = None
    haptics_enabled: bool | None = None
    voice_enabled: bool | None = None
    # C-21 通知偏好
    push_enabled: bool | None = None
    flashcard_reminder_enabled: bool | None = None
    daily_reminder_enabled: bool | None = None
    daily_reminder_time: str | None = None

    @field_validator("daily_reminder_time")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("daily_reminder_time must be HH:MM (e.g. '20:00')")
        return v
```

- [ ] **Step 4: Run schema test — verify it passes**

```
pytest tests/unit/test_notification_prefs.py -v
```
Expected: 2 PASS

- [ ] **Step 5: Add 4 columns to `app/models/user.py`**

After the `expo_push_token` line (line ~49), add:

```python
    # C-21 · 通知偏好
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    flashcard_reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    daily_reminder_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    daily_reminder_time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
```

- [ ] **Step 6: Create migration `alembic/versions/039_notification_prefs.py`**

```python
"""C-21 · 用户通知偏好字段

Revision ID: 039
Revises: 038
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("flashcard_reminder_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("daily_reminder_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("daily_reminder_time", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_reminder_time")
    op.drop_column("users", "daily_reminder_enabled")
    op.drop_column("users", "flashcard_reminder_enabled")
    op.drop_column("users", "push_enabled")
```

- [ ] **Step 7: Apply migration**

```
python -m alembic upgrade head
```
Expected: `Running upgrade 038 -> 039`

- [ ] **Step 8: Update `app/api/v1/user_prefs.py` to read/write new fields**

Replace the full file:

```python
"""用户 UI 偏好 API — v2 PRD 9.11 + C-21 通知偏好"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user_prefs import UserPrefsOut, UserPrefsUpdate

router = APIRouter(prefix="/profile/prefs", tags=["UI 偏好"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


def _to_out(user: User) -> UserPrefsOut:
    return UserPrefsOut(
        theme_mode=user.theme_mode,
        dynamic_type_scale=user.dynamic_type_scale,
        reduced_motion=user.reduced_motion,
        haptics_enabled=user.haptics_enabled,
        voice_enabled=user.voice_enabled,
        push_enabled=user.push_enabled,
        flashcard_reminder_enabled=user.flashcard_reminder_enabled,
        daily_reminder_enabled=user.daily_reminder_enabled,
        daily_reminder_time=user.daily_reminder_time,
    )


@router.get("", summary="读取当前 UI 偏好与通知设置")
async def get_prefs(
    user: User = Depends(get_current_user),
):
    return ok(_to_out(user).model_dump())


@router.patch("", summary="更新 UI 偏好与通知设置（任一字段可选）")
async def update_prefs(
    body: UserPrefsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return ok(_to_out(user).model_dump())
```

- [ ] **Step 9: Run all unit tests**

```
pytest tests/unit/ -v --tb=short -q
```
Expected: all pass (existing + 2 new)

- [ ] **Step 10: Commit**

```
git add alembic/versions/039_notification_prefs.py app/models/user.py app/schemas/user_prefs.py app/api/v1/user_prefs.py tests/unit/test_notification_prefs.py
git commit -m "feat(notif): C-21 notification prefs — 4 fields on User + prefs API extension (migration 039)"
```

---

## Task 2: Push Service (C-18) — extract + DeviceNotRegistered cleanup

**Files:**
- Create: `app/services/push_service.py`
- Modify: `app/services/notification_service.py`
- Create: `tests/unit/test_push_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_push_service.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_send_push_success():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"status": "ok", "id": "abc123"}]}

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[xxx]", "测试内容")

    assert result is None  # None = success


@pytest.mark.asyncio
async def test_send_push_device_not_registered():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [{"status": "error", "message": "...", "details": {"error": "DeviceNotRegistered"}}]
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(return_value=mock_resp)
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[stale]", "内容")

    assert result == "DeviceNotRegistered"


@pytest.mark.asyncio
async def test_send_push_network_error():
    import httpx
    with patch("httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        from app.services import push_service
        result = await push_service.send_push("ExponentPushToken[xxx]", "内容")

    assert result == "network_error"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/test_push_service.py -v
```
Expected: FAIL — `push_service` module not found

- [ ] **Step 3: Create `app/services/push_service.py`**

```python
"""Expo Push 发送服务 (C-18)

Returns None on success, error_type string on failure.
Callers handle DeviceNotRegistered by clearing the token.
"""
import logging
import httpx

logger = logging.getLogger(__name__)

_EXPO_URL = "https://exp.host/--/api/v2/push/send"


async def send_push(token: str, body: str) -> str | None:
    """Fire an Expo push notification.

    Returns None on success, or an error_type string:
      - "DeviceNotRegistered": token is stale; caller should clear it
      - "network_error": transient; safe to ignore
      - other string: Expo error details
    """
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _EXPO_URL,
                json={"to": token, "title": "知曜", "body": body, "sound": "default"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            tickets = resp.json().get("data", [])
            ticket = tickets[0] if tickets else {}
            if ticket.get("status") == "error":
                error_type = ticket.get("details", {}).get("error") or "unknown"
                logger.debug(f"Expo push error {error_type} for token …{token[-8:]}")
                return error_type
            return None
    except Exception as exc:
        logger.debug(f"Expo push network error: {exc}")
        return "network_error"
```

- [ ] **Step 4: Run push service tests**

```
pytest tests/unit/test_push_service.py -v
```
Expected: 3 PASS

- [ ] **Step 5: Update `app/services/notification_service.py` to use push_service**

Replace the `_send_expo_push` private function and the push call in `create()`. The file top stays the same. Make these two changes:

**Remove** the old private function (lines ~18-29):
```python
async def _send_expo_push(token: str, body: str) -> None:
    """Fire-and-forget Expo push. Failures are logged, never raised."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                "https://exp.host/--/api/v2/push/send",
                json={"to": token, "title": "知曜", "body": body, "sound": "default"},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
    except Exception as e:
        logger.debug(f"Expo push failed: {e}")
```

**Add** import at the top of the file (after existing imports):
```python
from app.services import push_service as _push_svc
```

**Replace** the push block inside `create()` (the section starting at `# Attempt Expo push (non-blocking)`):

Old code:
```python
        # Attempt Expo push (non-blocking)
        user_row = await db.execute(select(User).where(User.id == uid))
        user = user_row.scalar_one_or_none()
        if user and user.expo_push_token:
            await _send_expo_push(user.expo_push_token, content)
```

New code:
```python
        # Attempt Expo push — gated on push_enabled (C-21) + token present
        user_row = await db.execute(select(User).where(User.id == uid))
        user = user_row.scalar_one_or_none()
        if user and user.expo_push_token and user.push_enabled:
            error = await _push_svc.send_push(user.expo_push_token, content)
            if error == "DeviceNotRegistered":
                user.expo_push_token = None
                await db.commit()
```

- [ ] **Step 6: Add push_enabled gate test to `tests/unit/test_notification_prefs.py`**

Append to the file:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
    await svc.create(fake_db, str(fake_user.id), "测试", "test_type")

    assert push_called == [], "push should NOT be called when push_enabled=False"
```

- [ ] **Step 7: Run all unit tests**

```
pytest tests/unit/ -v --tb=short -q
```
Expected: all pass

- [ ] **Step 8: Commit**

```
git add app/services/push_service.py app/services/notification_service.py tests/unit/test_push_service.py tests/unit/test_notification_prefs.py
git commit -m "feat(notif): C-18 push_service.py — extract Expo push + DeviceNotRegistered cleanup + push_enabled gate"
```

---

## Task 3: FSRS Review Due Task (C-17 / C-19)

**Files:**
- Create: `app/tasks/review_due_tasks.py`
- Modify: `app/tasks/celery_app.py`
- Create: `tests/unit/test_review_due_tasks.py`

- [ ] **Step 1: Write failing tests (pure-function guard logic)**

```python
# tests/unit/test_review_due_tasks.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/test_review_due_tasks.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Create `app/tasks/review_due_tasks.py`**

```python
"""C-17/C-19 · FSRS 复习到期推送

调度：Celery beat 每小时 :30 分。
扫描规则：
  - 闪卡 due_date <= today
  - user.flashcard_reminder_enabled = True
  - 今日内未推过同类通知（8h 去重）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_NOTIF_TYPE = "fsrs_review_due"
_DEDUP_HOURS = 8


def should_send_review_reminder(
    due_count: int,
    flashcard_reminder_enabled: bool,
    hours_since_last_reminder: float | None,
) -> bool:
    """Pure guard — no DB, fully testable."""
    if not flashcard_reminder_enabled:
        return False
    if due_count <= 0:
        return False
    if hours_since_last_reminder is not None and hours_since_last_reminder < _DEDUP_HOURS:
        return False
    return True


def review_due_message(count: int) -> str:
    if count == 1:
        return "有1张复习卡今天到期了，顺手看一眼吧"
    elif count <= 10:
        return f"有{count}张复习卡今天到期了，别让它们积起来"
    else:
        return f"{count}张卡到期了，今天找个时间清一清"


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.review_due_tasks.scan_review_due")
def scan_review_due():
    """每小时扫描 FSRS 到期闪卡 → 推送复习提醒"""
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.flashcard import Flashcard
    from app.models.user import User
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    now = datetime.now(timezone.utc)
    today = date.today()
    cutoff = now - timedelta(hours=_DEDUP_HOURS)

    pushed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        # All users with push_enabled + flashcard_reminder_enabled + onboarding done
        users_result = await db.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.flashcard_reminder_enabled.is_(True),
                User.push_enabled.is_(True),
                User.expo_push_token.isnot(None),
            )
        )
        users = list(users_result.scalars().all())

    notif_svc = NotificationService()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                # Count due cards
                due_result = await db.execute(
                    select(func.count()).select_from(Flashcard).where(
                        Flashcard.user_id == user.id,
                        Flashcard.due_date <= today,
                    )
                )
                due_count = int(due_result.scalar_one() or 0)

                # Hours since last reminder of this type
                last_result = await db.execute(
                    select(func.max(Notification.created_at)).where(
                        Notification.user_id == user.id,
                        Notification.notification_type == _NOTIF_TYPE,
                    )
                )
                last_at = last_result.scalar_one()
                hours_since = (
                    (now - last_at).total_seconds() / 3600
                    if last_at and last_at.tzinfo
                    else None
                )

                if not should_send_review_reminder(due_count, True, hours_since):
                    skipped += 1
                    continue

                await notif_svc.create(
                    db,
                    user_id=str(user.id),
                    content=review_due_message(due_count),
                    notification_type=_NOTIF_TYPE,
                    related_action="/flashcards",
                )
                pushed += 1
        except Exception as exc:
            logger.warning(f"review_due push failed for user {user.id}: {exc}")
            skipped += 1

    logger.info(f"scan_review_due: pushed={pushed} skipped={skipped}")
    return {"pushed": pushed, "skipped": skipped}
```

- [ ] **Step 4: Run tests — verify they pass**

```
pytest tests/unit/test_review_due_tasks.py -v
```
Expected: 7 PASS

- [ ] **Step 5: Register the task in `app/tasks/celery_app.py`**

Add `"app.tasks.review_due_tasks"` to the `include` list (after `learning_kernel_tasks`):
```python
        "app.tasks.review_due_tasks",    # C-17/C-19 · FSRS 到期复习推送
```

Add beat schedule entry inside `beat_schedule` dict (after the mastery-calibration entry):
```python
        # C-17/C-19 · FSRS 复习到期推送（每小时 :30 分）
        "scan-review-due": {
            "task": "app.tasks.review_due_tasks.scan_review_due",
            "schedule": crontab(minute=30) if settings.APP_ENV != "development" else 3600.0,
        },
```

- [ ] **Step 6: Run all unit tests**

```
pytest tests/unit/ -v --tb=short -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add app/tasks/review_due_tasks.py app/tasks/celery_app.py tests/unit/test_review_due_tasks.py
git commit -m "feat(notif): C-17/C-19 FSRS review-due hourly task — scan + push + 8h dedup"
```

---

## Task 4: Daily Checkin Reminder (C-20)

**Files:**
- Create: `app/tasks/checkin_reminder_tasks.py`
- Modify: `app/tasks/celery_app.py`
- Create: `tests/unit/test_checkin_reminder_tasks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_checkin_reminder_tasks.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/unit/test_checkin_reminder_tasks.py -v
```
Expected: FAIL — module not found

- [ ] **Step 3: Create `app/tasks/checkin_reminder_tasks.py`**

```python
"""C-20 · 每日打卡提醒

调度：Celery beat 每小时 :50 分。
规则：
  - user.daily_reminder_enabled = True
  - user.daily_reminder_time 与当前北京时间小时匹配
  - 今日尚未打卡
  - 23h 去重（防止同日重复推送）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_NOTIF_TYPE = "daily_checkin_reminder"
_DEDUP_HOURS = 23


def should_send_checkin_reminder(
    daily_reminder_enabled: bool,
    daily_reminder_time: str | None,
    current_bj_hour: int,
    checked_in_today: bool,
    hours_since_last_reminder: float | None,
) -> bool:
    """Pure guard — no DB, fully testable."""
    if not daily_reminder_enabled or not daily_reminder_time:
        return False
    if checked_in_today:
        return False
    if hours_since_last_reminder is not None and hours_since_last_reminder < _DEDUP_HOURS:
        return False
    try:
        target_hour = int(daily_reminder_time.split(":")[0])
    except (ValueError, IndexError, AttributeError):
        return False
    return current_bj_hour == target_hour


def _run(coro):
    from app.core.database import engine
    import app.core.redis as _redis_mod
    engine.sync_engine.dispose()
    _redis_mod._redis_pool = None
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.checkin_reminder_tasks.scan_checkin_reminder")
def scan_checkin_reminder():
    """每小时扫描：用户设定时间到 → 未打卡 → 推送提醒"""
    return _run(_scan_async())


async def _scan_async() -> dict:
    from sqlalchemy import select, func
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.checkin import CheckIn
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    now = datetime.now(timezone.utc)
    bj_now = now + timedelta(hours=8)
    current_bj_hour = bj_now.hour
    today_bj = bj_now.date()
    today_start_utc = datetime(today_bj.year, today_bj.month, today_bj.day,
                               tzinfo=timezone.utc) - timedelta(hours=8)

    pushed = 0
    skipped = 0

    async with AsyncSessionLocal() as db:
        users_result = await db.execute(
            select(User).where(
                User.onboarding_completed.is_(True),
                User.daily_reminder_enabled.is_(True),
                User.daily_reminder_time.isnot(None),
                User.push_enabled.is_(True),
                User.expo_push_token.isnot(None),
            )
        )
        users = list(users_result.scalars().all())

    notif_svc = NotificationService()

    for user in users:
        try:
            async with AsyncSessionLocal() as db:
                # Checked in today?
                checkin_result = await db.execute(
                    select(func.count()).select_from(CheckIn).where(
                        CheckIn.user_id == user.id,
                        CheckIn.created_at >= today_start_utc,
                    )
                )
                checked_in = int(checkin_result.scalar_one() or 0) > 0

                # Hours since last reminder
                last_result = await db.execute(
                    select(func.max(Notification.created_at)).where(
                        Notification.user_id == user.id,
                        Notification.notification_type == _NOTIF_TYPE,
                    )
                )
                last_at = last_result.scalar_one()
                hours_since = (
                    (now - last_at).total_seconds() / 3600
                    if last_at and last_at.tzinfo
                    else None
                )

                if not should_send_checkin_reminder(
                    True, user.daily_reminder_time, current_bj_hour, checked_in, hours_since
                ):
                    skipped += 1
                    continue

                await notif_svc.create(
                    db,
                    user_id=str(user.id),
                    content="今天还没打卡，趁现在记录一下学了什么",
                    notification_type=_NOTIF_TYPE,
                    related_action="/checkin",
                )
                pushed += 1
        except Exception as exc:
            logger.warning(f"checkin_reminder failed for user {user.id}: {exc}")
            skipped += 1

    logger.info(f"scan_checkin_reminder: pushed={pushed} skipped={skipped}")
    return {"pushed": pushed, "skipped": skipped}
```

- [ ] **Step 4: Run tests — verify they pass**

```
pytest tests/unit/test_checkin_reminder_tasks.py -v
```
Expected: 8 PASS

- [ ] **Step 5: Register in `app/tasks/celery_app.py`**

Add to the `include` list (after `review_due_tasks`):
```python
        "app.tasks.checkin_reminder_tasks",  # C-20 · 每日打卡提醒
```

Add to `beat_schedule` dict (after `scan-review-due`):
```python
        # C-20 · 每日打卡提醒（每小时 :50 分）
        "scan-checkin-reminder": {
            "task": "app.tasks.checkin_reminder_tasks.scan_checkin_reminder",
            "schedule": crontab(minute=50) if settings.APP_ENV != "development" else 3600.0,
        },
```

- [ ] **Step 6: Run all unit tests**

```
pytest tests/unit/ -v --tb=short -q
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add app/tasks/checkin_reminder_tasks.py app/tasks/celery_app.py tests/unit/test_checkin_reminder_tasks.py
git commit -m "feat(notif): C-20 daily checkin reminder — user-scheduled hourly scan + 23h dedup"
```

---

## Task 5: Update Docs

**Files:**
- Modify: `SPEC.md` (Section 0 + Section 4.18/4.23 or new 4.26)
- Modify: `V3_PRD_FRAMEWORK.md` (C-17~C-21, F-12 already done)

- [ ] **Step 1: Update `SPEC.md` Section 0**

Update the table row:
- Alembic head: `039`
- pytest: (run full suite first, update count)
- API 总端点: add note about C-17~C-21 push pipeline

- [ ] **Step 2: Add/update Section 4 entry for notification preferences**

Add under Section 4.18 (通知 `/v1/notifications`) the note about new push prefs fields available via `PATCH /v1/profile/prefs`:
```
**C-21 通知偏好字段（通过 PATCH /v1/profile/prefs 写入）：**
- `push_enabled: bool` — 全局推送开关（默认 true）
- `flashcard_reminder_enabled: bool` — FSRS 到期推送（默认 true）
- `daily_reminder_enabled: bool` — 每日打卡提醒（默认 false）
- `daily_reminder_time: "HH:MM" | null` — 打卡提醒时间（北京时间，如 "20:00"）
```

- [ ] **Step 3: Update `V3_PRD_FRAMEWORK.md`**

Mark C-17, C-18, C-19, C-20, C-21 as ✅, update progress totals and changelog entry.

- [ ] **Step 4: Run full test suite, record count**

```
pytest --tb=short -q
```
Record the pass count for SPEC.md Section 0.

- [ ] **Step 5: Commit docs**

```
git add SPEC.md V3_PRD_FRAMEWORK.md
git commit -m "docs: C-17~C-21 push notifications pipeline complete — prefs/push_service/review_due/checkin_reminder"
```

---

## Self-Review

**Spec coverage check:**
- C-17 Agent 主动推送 → `review_due_tasks.py` Celery beat 每小时扫描 FSRS due ✅
- C-18 Expo 接入 → `push_service.py` 提取 + DeviceNotRegistered 处理 ✅
- C-19 复习到期通知 → `review_due_tasks.py` 同 C-17 ✅
- C-20 每日打卡提醒 → `checkin_reminder_tasks.py` 用户配置时间 ✅
- C-21 通知偏好真实写入 → migration 039 + prefs API + push gate ✅

**No placeholders:** All code blocks contain complete implementations. No "TBD" or "handle edge cases".

**Type consistency:**
- `should_send_review_reminder(due_count, flashcard_reminder_enabled, hours_since_last_reminder)` — same signature in task file and test file ✅
- `should_send_checkin_reminder(daily_reminder_enabled, daily_reminder_time, current_bj_hour, checked_in_today, hours_since_last_reminder)` — same in both ✅
- `push_service.send_push(token, body) -> str | None` — same in push_service.py, test_push_service.py, and notification_service.py call site ✅
- `UserPrefsOut` fields match `user_prefs.py` `_to_out()` function ✅
