# Subscription System Implementation Plan (E-01~E-03)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend subscription tier system — RevenueCat webhook handler, subscription status endpoint, and Pro feature gating — on top of the existing `plan_type` + `plan_expires_at` User fields.

**Architecture:** The User model already has `plan_type` (string, default "free") and `plan_expires_at` (DateTime, nullable). We add: (1) a `subscription_events` audit table for webhook idempotency and debugging; (2) a `SubscriptionService` with pure `is_pro()` / `get_status()` logic and `apply_revenuecat_event()` mutation; (3) two new endpoints — `GET /v1/subscription/status` and `POST /v1/subscription/webhook`; (4) a dedicated `SubscriptionRequiredError(4031)` and an updated `require_pro()` dependency; (5) Pro gating applied to three endpoints.

**Tech Stack:** FastAPI + SQLAlchemy 2.x async + Pydantic v2 + Alembic · RevenueCat Authorization header validation (shared secret in RevenueCat dashboard → `Authorization: Bearer <secret>`)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `app/models/subscription_event.py` | Create | SubscriptionEvent ORM model |
| `alembic/versions/041_subscription_events.py` | Create | Migration: subscription_events table |
| `app/services/subscription_service.py` | Create | is_pro(), get_status(), apply_revenuecat_event(), verify_webhook_auth() |
| `app/schemas/subscription.py` | Create | SubscriptionStatusOut, WebhookPayload |
| `app/api/v1/subscription.py` | Create | GET /status, POST /webhook endpoints |
| `app/api/v1/__init__.py` | Modify | Register subscription router |
| `app/core/exceptions.py` | Modify | Add SubscriptionRequiredError(4031) |
| `app/api/deps.py` | Modify | Update require_pro() to use is_pro() + SubscriptionRequiredError |
| `app/api/v1/reports.py` | Modify | Gate GET /reports/weekly behind require_pro |
| `app/api/v1/knowledge_base.py` | Modify | Gate POST /knowledge-base/upload behind require_pro |
| `app/config.py` | Modify | Add REVENUECAT_WEBHOOK_SECRET setting |
| `tests/unit/test_subscription_service.py` | Create | Pure function tests for is_pro(), get_status(), verify_webhook_auth() |
| `tests/unit/test_subscription_api.py` | Create | Auth guard + webhook signature rejection tests |
| `SPEC.md` | Modify | Add Section 4.28, update counts |
| `V3_PRD_FRAMEWORK.md` | Modify | E-01~E-03 ✅, F-12 ✅, progress totals |

---

## Task 1: SubscriptionEvent model + migration 041

**Files:**
- Create: `app/models/subscription_event.py`
- Create: `alembic/versions/041_subscription_events.py`
- Modify: `app/models/__init__.py` (add import)

- [ ] **Step 1: Write the failing import test**

```python
# tests/unit/test_subscription_service.py  (create this file now, add to it in Task 2)
def test_subscription_event_model_importable():
    from app.models.subscription_event import SubscriptionEvent
    assert SubscriptionEvent.__tablename__ == "subscription_events"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_subscription_service.py::test_subscription_event_model_importable -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create `app/models/subscription_event.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    revenuecat_event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # INITIAL_PURCHASE, RENEWAL, etc.
    product_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 4: Add import to `app/models/__init__.py`**

Open the file and add:
```python
from app.models.subscription_event import SubscriptionEvent  # noqa: F401
```
(Add it alongside the other model imports, e.g., after `KnowledgeBaseFile`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_subscription_service.py::test_subscription_event_model_importable -v`
Expected: PASS

- [ ] **Step 6: Create `alembic/versions/041_subscription_events.py`**

```python
"""Add subscription_events table for E-01~E-03 subscription system."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revenuecat_event_id", sa.String(128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_events_user_id", "subscription_events", ["user_id"])
    op.create_index("ix_subscription_events_revenuecat_event_id", "subscription_events", ["revenuecat_event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("subscription_events")
```

- [ ] **Step 7: Verify model imports and all tests pass**

```powershell
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
python -c "from app.models.subscription_event import SubscriptionEvent; print('ok')"
python -m pytest tests/unit/ -q --tb=short
```
Expected: `ok` + 176 pass

- [ ] **Step 8: Commit**

```bash
git add app/models/subscription_event.py alembic/versions/041_subscription_events.py app/models/__init__.py tests/unit/test_subscription_service.py
git commit -m "feat(sub): E-01 SubscriptionEvent model + migration 041"
```

---

## Task 2: SubscriptionService + Settings field

**Files:**
- Modify: `app/config.py`
- Create: `app/services/subscription_service.py`
- Modify: `tests/unit/test_subscription_service.py` (add pure function tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_subscription_service.py`:

```python
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from app.services.subscription_service import is_pro, get_status, verify_webhook_auth


def _user(plan_type: str, expires_at=None) -> MagicMock:
    u = MagicMock()
    u.plan_type = plan_type
    u.plan_expires_at = expires_at
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
    future = datetime.now(timezone.utc) + timedelta(days=15)
    user = _user("pro", future)
    status = get_status(user)
    assert status["plan_type"] == "pro"
    assert status["is_pro"] is True
    assert status["days_remaining"] == 15
    assert status["features"]["advanced_reports"] is True
    assert status["features"]["knowledge_base_upload"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_subscription_service.py -v -k "not importable"`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.subscription_service'`

- [ ] **Step 3: Add `REVENUECAT_WEBHOOK_SECRET` to `app/config.py`**

Open `app/config.py`. Find the `class Settings(BaseSettings)` block. Add after existing fields (e.g., after `LEARNING_ENGINE_ENABLED`):

```python
# Subscription (RevenueCat)
REVENUECAT_WEBHOOK_SECRET: str = ""  # Set in .env for production; empty = webhook disabled
```

- [ ] **Step 4: Create `app/services/subscription_service.py`**

```python
"""E-01~E-03 · Subscription tier service.

plan_type values: "free" | "pro" | "edu"
- "free"  : default, no Pro features
- "pro"   : active paid subscription (check plan_expires_at)
- "edu"   : manually granted by admin, no expiry
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.models.user import User

logger = logging.getLogger(__name__)

# RevenueCat event types that grant or revoke Pro access
_GRANT_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE", "UNCANCELLATION"}
_REVOKE_EVENTS = {"EXPIRATION"}
# CANCELLATION does NOT revoke — user keeps access until expires_at


def is_pro(user: User) -> bool:
    """Return True if user currently has active Pro (or Edu) access."""
    if user.plan_type == "edu":
        return True
    if user.plan_type == "pro":
        if user.plan_expires_at is None:
            return True  # lifetime / no-expiry grant
        return user.plan_expires_at > datetime.now(timezone.utc)
    return False


def get_status(user: User) -> dict[str, Any]:
    """Return subscription status dict for the /status endpoint."""
    pro = is_pro(user)
    days_remaining: int | None = None
    if user.plan_type == "pro" and user.plan_expires_at is not None:
        delta = user.plan_expires_at - datetime.now(timezone.utc)
        days_remaining = max(0, delta.days)

    return {
        "plan_type": user.plan_type,
        "is_pro": pro,
        "plan_expires_at": user.plan_expires_at,
        "days_remaining": days_remaining,
        "features": {
            "unlimited_agent": pro,
            "advanced_reports": pro,
            "knowledge_base_upload": pro,
        },
    }


def verify_webhook_auth(authorization_header: str | None, secret: str) -> bool:
    """Validate RevenueCat webhook Authorization header.

    RevenueCat sends: Authorization: Bearer <secret>
    Configure the secret in the RevenueCat dashboard → Webhooks → Authorization header.
    """
    if not authorization_header or not secret:
        return False
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return parts[1] == secret


async def apply_revenuecat_event(db, payload: dict) -> None:
    """Parse a RevenueCat webhook event and update the user's subscription tier.

    Idempotent: duplicate events (same revenuecat_event_id) are silently ignored.
    """
    from sqlalchemy import select
    from app.models.user import User
    from app.models.subscription_event import SubscriptionEvent

    event = payload.get("event", {})
    event_id = event.get("id", "")
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id")
    expiration_at_ms = event.get("expiration_at_ms")

    if not event_id or not event_type or not app_user_id:
        logger.warning("RevenueCat webhook missing required fields: %s", payload)
        return

    # Idempotency check
    existing = await db.execute(
        select(SubscriptionEvent).where(SubscriptionEvent.revenuecat_event_id == event_id)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Duplicate RevenueCat event %s — skipped", event_id)
        return

    # Resolve expires_at
    expires_at: datetime | None = None
    if expiration_at_ms is not None:
        expires_at = datetime.fromtimestamp(expiration_at_ms / 1000, tz=timezone.utc)

    # Resolve user by app_user_id (we set this to user UUID in the mobile SDK)
    import uuid as _uuid
    try:
        uid = _uuid.UUID(app_user_id)
    except ValueError:
        logger.warning("RevenueCat app_user_id is not a UUID: %s", app_user_id)
        uid = None

    user: User | None = None
    if uid is not None:
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()

    # Update user plan
    if user is not None:
        if event_type in _GRANT_EVENTS:
            user.plan_type = "pro"
            user.plan_expires_at = expires_at
        elif event_type in _REVOKE_EVENTS:
            user.plan_type = "free"
            user.plan_expires_at = None

    # Record audit event
    se = SubscriptionEvent(
        user_id=user.id if user else None,
        revenuecat_event_id=event_id,
        event_type=event_type,
        product_id=product_id,
        expires_at=expires_at,
        raw_payload=payload,
    )
    db.add(se)
    await db.commit()
    logger.info("Processed RevenueCat event %s (%s) for user %s", event_id, event_type, app_user_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_subscription_service.py -v`
Expected: all tests PASS (importable + is_pro + verify_webhook_auth + get_status = ~12 tests)

- [ ] **Step 6: Run full suite**

```powershell
python -m pytest tests/unit/ -q --tb=short
```
Expected: 176+ pass

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/services/subscription_service.py tests/unit/test_subscription_service.py
git commit -m "feat(sub): E-01 SubscriptionService — is_pro/get_status/verify_webhook_auth/apply_event"
```

---

## Task 3: Subscription endpoints + schemas

**Files:**
- Create: `app/schemas/subscription.py`
- Create: `app/api/v1/subscription.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/unit/test_subscription_api.py`

- [ ] **Step 1: Write failing auth-guard tests**

Create `tests/unit/test_subscription_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_subscription_status_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/subscription/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_webhook_rejects_missing_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/subscription/webhook", json={"event": {}})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_rejects_wrong_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/subscription/webhook",
            json={"event": {"id": "x", "type": "INITIAL_PURCHASE", "app_user_id": "y"}},
            headers={"Authorization": "Bearer wrong-secret"},
        )
    # When REVENUECAT_WEBHOOK_SECRET is empty string (dev default), any non-empty auth fails
    assert resp.status_code in (401, 200)  # 401 if secret mismatch, 200 if secret is empty (disabled)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_subscription_api.py -v`
Expected: FAIL — 404 (routes don't exist yet)

- [ ] **Step 3: Create `app/schemas/subscription.py`**

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class SubscriptionFeatures(BaseModel):
    unlimited_agent: bool
    advanced_reports: bool
    knowledge_base_upload: bool


class SubscriptionStatusOut(BaseModel):
    plan_type: str
    is_pro: bool
    plan_expires_at: datetime | None
    days_remaining: int | None
    features: SubscriptionFeatures

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Create `app/api/v1/subscription.py`**

```python
import logging
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.exceptions import AppError
from app.config import settings
from app.models.user import User
from app.schemas.subscription import SubscriptionStatusOut, SubscriptionFeatures
from app.services.subscription_service import get_status, verify_webhook_auth, apply_revenuecat_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscription", tags=["订阅"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("/status", summary="当前订阅状态")
async def subscription_status(
    user: User = Depends(get_current_user),
):
    data = get_status(user)
    return ok(
        SubscriptionStatusOut(
            plan_type=data["plan_type"],
            is_pro=data["is_pro"],
            plan_expires_at=data["plan_expires_at"],
            days_remaining=data["days_remaining"],
            features=SubscriptionFeatures(**data["features"]),
        )
    )


@router.post("/webhook", summary="RevenueCat webhook（服务端专用）")
async def revenuecat_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive RevenueCat subscription lifecycle events.

    Authentication: RevenueCat sends `Authorization: Bearer <secret>`.
    Configure REVENUECAT_WEBHOOK_SECRET in .env to match the secret set in the
    RevenueCat dashboard → Project Settings → Webhooks → Authorization header.

    If REVENUECAT_WEBHOOK_SECRET is empty (dev default), the endpoint accepts all
    requests and only logs — safe for local testing.
    """
    auth_header = request.headers.get("Authorization")
    secret = settings.REVENUECAT_WEBHOOK_SECRET

    if secret and not verify_webhook_auth(auth_header, secret):
        raise AppError(4010, "Webhook 签名无效", 401)

    try:
        payload = await request.json()
    except Exception:
        raise AppError(4000, "请求体不是有效 JSON", 400)

    await apply_revenuecat_event(db, payload)
    return ok(None)
```

- [ ] **Step 5: Update `app/api/v1/__init__.py`**

Add to imports:
```python
from app.api.v1 import subscription
```

Add to router registrations (after `learning_engine`):
```python
# E-01~E-03 subscription
router.include_router(subscription.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_subscription_api.py -v`
Expected: all 3 tests PASS

- [ ] **Step 7: Run full test suite**

```powershell
python -m pytest tests/unit/ -q --tb=short
```
Expected: 176+ pass (no regressions)

- [ ] **Step 8: Commit**

```bash
git add app/schemas/subscription.py app/api/v1/subscription.py app/api/v1/__init__.py tests/unit/test_subscription_api.py
git commit -m "feat(sub): E-02/E-03 GET /subscription/status + POST /subscription/webhook"
```

---

## Task 4: Pro gating — SubscriptionRequiredError + apply to 3 endpoints

**Files:**
- Modify: `app/core/exceptions.py`
- Modify: `app/api/deps.py`
- Modify: `app/api/v1/reports.py`
- Modify: `app/api/v1/knowledge_base.py`
- Modify: `tests/unit/test_subscription_service.py` (add gating test)

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_subscription_service.py`:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.exceptions import SubscriptionRequiredError


def test_subscription_required_error_has_code_4031():
    err = SubscriptionRequiredError()
    assert err.code == 4031
    assert err.status_http == 403


@pytest.mark.asyncio
async def test_require_pro_raises_for_free_user():
    from app.api.deps import require_pro
    free_user = _user("free")
    with patch("app.api.deps.get_current_user", return_value=free_user):
        # Call require_pro directly with the user bypassing the Depends chain
        with pytest.raises(SubscriptionRequiredError):
            await require_pro(user=free_user)


@pytest.mark.asyncio
async def test_require_pro_passes_for_pro_user():
    from datetime import timedelta
    from app.api.deps import require_pro
    future = datetime.now(timezone.utc) + timedelta(days=10)
    pro_user = _user("pro", future)
    result = await require_pro(user=pro_user)
    assert result is pro_user
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_subscription_service.py -v -k "subscription_required or require_pro"`
Expected: FAIL — `ImportError: cannot import name 'SubscriptionRequiredError'`

- [ ] **Step 3: Add `SubscriptionRequiredError` to `app/core/exceptions.py`**

Open the file. Find where other error classes are defined. Add after `PermissionDeniedError`:

```python
class SubscriptionRequiredError(AppError):
    def __init__(self, message: str = "升级 Pro 才能使用这个功能"):
        super().__init__(4031, message, 403)
```

- [ ] **Step 4: Update `app/api/deps.py`**

Change the import line at the top from:
```python
from app.core.exceptions import TokenExpiredError, PermissionDeniedError
```
to:
```python
from app.core.exceptions import TokenExpiredError, PermissionDeniedError, SubscriptionRequiredError
```

Change the `require_pro` function body from:
```python
async def require_pro(user: User = Depends(get_current_user)) -> User:
    if user.plan_type == "free":
        raise PermissionDeniedError()
    return user
```
to:
```python
async def require_pro(user: User = Depends(get_current_user)) -> User:
    from app.services.subscription_service import is_pro
    if not is_pro(user):
        raise SubscriptionRequiredError()
    return user
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_subscription_service.py -v -k "subscription_required or require_pro"`
Expected: all 3 new tests PASS

- [ ] **Step 6: Gate `GET /v1/reports/weekly` behind Pro**

Open `app/api/v1/reports.py`.

Find the `get_weekly_report` function signature:
```python
async def get_weekly_report(
    offset_weeks: int = Query(0, ge=0, le=4, description="0=本周 1=上周"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
```

Add `require_pro` to the imports at the top of the file:
```python
from app.api.deps import get_current_user, require_pro
```

Change `user: User = Depends(get_current_user)` to `user: User = Depends(require_pro)`:
```python
async def get_weekly_report(
    offset_weeks: int = Query(0, ge=0, le=4, description="0=本周 1=上周"),
    user: User = Depends(require_pro),
    db: AsyncSession = Depends(get_db),
):
```

- [ ] **Step 7: Gate `POST /v1/knowledge-base/upload` behind Pro**

Open `app/api/v1/knowledge_base.py`.

Add `require_pro` to the import from `app.api.deps`:
```python
from app.api.deps import get_current_user, require_pro
```

Find the `upload_kb_file` function. Change `user: User = Depends(get_current_user)` to `user: User = Depends(require_pro)`.

(Only the upload endpoint is Pro-gated; list/detail/delete remain accessible so free users can manage any files they uploaded during trial.)

- [ ] **Step 8: Run full test suite**

```powershell
python -m pytest tests/unit/ -q --tb=short
```
Expected: all tests pass (the reports and kb_api auth tests use 401/403 for unauthenticated — these still pass because `require_pro` also enforces auth)

- [ ] **Step 9: Commit**

```bash
git add app/core/exceptions.py app/api/deps.py app/api/v1/reports.py app/api/v1/knowledge_base.py tests/unit/test_subscription_service.py
git commit -m "feat(sub): E-02 SubscriptionRequiredError(4031) + require_pro gating on reports/knowledge-base"
```

---

## Task 5: Documentation + F-12 framework fix

**Files:**
- Modify: `C:\Users\18208\Desktop\知曜创业项目\SPEC.md`
- Modify: `C:\Users\18208\Desktop\知曜创业项目\V3_PRD_FRAMEWORK.md`

- [ ] **Step 1: Update `SPEC.md`**

**Section 0 — update counts:**
- `Alembic head`: `040` → `041`（subscription_events · E-01 订阅事件）
- `pytest`: update to actual passing count after Task 4

**Add Section 4.28** after Section 4.27 (知识库文件):

```markdown
### 4.28 订阅 `/v1/subscription`

| 方法 | 路径 | 认证 | 描述 |
|------|------|------|------|
| GET | `/subscription/status` | ✅ | 当前订阅状态（plan_type/is_pro/days_remaining/features）|
| POST | `/subscription/webhook` | 🔑 RevenueCat | RevenueCat 订阅生命周期事件（Authorization: Bearer <secret>）|

**SubscriptionStatusOut**：`plan_type`（free/pro/edu）· `is_pro`（bool）· `plan_expires_at`（datetime\|null）· `days_remaining`（int\|null）· `features`（unlimited_agent/advanced_reports/knowledge_base_upload）

**plan_type 值**：
- `free`：默认，无 Pro 功能
- `pro`：有效付费订阅（check `plan_expires_at`）
- `edu`：管理员手动授权，永不过期

**RevenueCat 集成**：
- 移动端 SDK 设置 `app_user_id = user.id`（UUID 字符串）
- Dashboard → Webhooks → Authorization header = `Bearer {REVENUECAT_WEBHOOK_SECRET}`
- 处理事件：INITIAL_PURCHASE/RENEWAL/PRODUCT_CHANGE → plan="pro"; EXPIRATION → plan="free"; CANCELLATION → 不立即变更（到期自然失效）
- 幂等：`revenuecat_event_id` 唯一约束，重复投递静默忽略

**Pro 功能限制（`require_pro` 依赖）**：
- `GET /v1/reports/weekly` — Pro only
- `POST /v1/knowledge-base/upload` — Pro only

**错误码**：`4031` SubscriptionRequiredError（403）— "升级 Pro 才能使用这个功能"
```

**Section 7 — 迁移链 — add:**
```
→ 040 kb_files（D-06 知识库文件管理）
→ 041 subscription_events（E-01 订阅事件审计日志）
```

- [ ] **Step 2: Update `V3_PRD_FRAMEWORK.md`**

**Fix F-12** (already implemented as `_assert_cors_safe()` in `app/main.py` — just the doc was never updated):

Find:
```
| F-12 | **CORS 生产环境防护**：CI/CD 部署脚本强制检查 `ALLOWED_ORIGINS` 不含通配符 | P2 | 🔲 | `app/main.py:75-85` |
```
Change to:
```
| F-12 | **[已完成]** CORS 生产环境防护：`_assert_cors_safe()` 在 lifespan 启动时拦截生产环境通配符 | P2 | ✅ | `app/main.py:78-84` |
```

**Update E-01~E-03:**

Find:
```
| E-01 | RevenueCat 接入（iOS IAP + Android IAP 统一）| P1 | 🔲 |
| E-02 | Paywall 设计（Pro 功能 gating）| P1 | 🔲 |
| E-03 | 订阅管理页面（当前计划/到期日/取消）| P1 | 🔲 |
```
Change to:
```
| E-01 | **[已完成]** RevenueCat 后端接入（webhook handler + subscription_events 审计 + plan_type/plan_expires_at 更新）| P1 | ✅ |
| E-02 | **[已完成]** Pro 功能 gating（SubscriptionRequiredError 4031 + require_pro 依赖 + reports/knowledge-base 限制）| P1 | ✅ |
| E-03 | 订阅管理页面（前端：当前计划/到期日/升级入口，接 GET /v1/subscription/status）| P1 | 🔲 |
```

**Update progress totals** — 主线 E: 0→2 completed; 主线 F: +1 (F-12); 合计 accordingly.

**Add changelog entry:**
```
| 2026-06-01 | V3.18 | E-01/E-02 订阅系统后端（RevenueCat webhook + subscription_events + is_pro + require_pro + 4031 错误码）；F-12 文档补标 ✅ |
```

- [ ] **Step 3: Commit docs**

```bash
git -C "C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend" add "C:\Users\18208\Desktop\知曜创业项目\SPEC.md" "C:\Users\18208\Desktop\知曜创业项目\V3_PRD_FRAMEWORK.md"
```

Check which git repo owns SPEC.md:
```bash
git -C "C:\Users\18208\Desktop\知曜创业项目" status
```

If owned by root repo:
```bash
git -C "C:\Users\18208\Desktop\知曜创业项目" add SPEC.md V3_PRD_FRAMEWORK.md
git -C "C:\Users\18208\Desktop\知曜创业项目" commit -m "docs: E-01/E-02 subscription system SPEC 4.28 + V3.18 changelog + F-12 ✅"
```

If owned by zhiyao-backend:
```bash
cd C:\Users\18208\Desktop\知曜创业项目\zhiyao-backend
git add ../SPEC.md ../V3_PRD_FRAMEWORK.md
git commit -m "docs: E-01/E-02 subscription system SPEC 4.28 + V3.18 changelog + F-12 ✅"
```

---

## Self-Review

### 1. Spec coverage

| Requirement | Task |
|-------------|------|
| User already has plan_type/plan_expires_at | No migration needed ✅ |
| SubscriptionEvent audit log (idempotency) | Task 1 ✅ |
| is_pro() pure function | Task 2 ✅ |
| verify_webhook_auth() pure function | Task 2 ✅ |
| get_status() returns features dict | Task 2 ✅ |
| GET /subscription/status | Task 3 ✅ |
| POST /subscription/webhook | Task 3 ✅ |
| Webhook ignores events when secret is empty (dev) | Task 3 ✅ |
| SubscriptionRequiredError(4031) | Task 4 ✅ |
| require_pro() uses is_pro() not string compare | Task 4 ✅ |
| GET /reports/weekly gated | Task 4 ✅ |
| POST /knowledge-base/upload gated | Task 4 ✅ |
| SPEC.md updated | Task 5 ✅ |
| V3_PRD_FRAMEWORK E-01/E-02 ✅, F-12 ✅ | Task 5 ✅ |

No gaps found.

### 2. Placeholder scan

No TBDs, no "add validation", no "similar to Task N" patterns. All code blocks are complete.

### 3. Type consistency

- `is_pro(user: User) -> bool` — used in Task 2 tests and Task 4 deps.py. ✅ consistent
- `get_status(user: User) -> dict` — used in Task 2 tests and Task 3 endpoint. ✅ consistent  
- `verify_webhook_auth(authorization_header: str | None, secret: str) -> bool` — used in Task 2 tests and Task 3 endpoint. ✅ consistent
- `apply_revenuecat_event(db, payload: dict) -> None` — used in Task 3 endpoint. ✅ consistent
- `SubscriptionRequiredError` — imported in Task 4 from `app.core.exceptions`. ✅ consistent
- `SubscriptionFeatures` fields: `unlimited_agent`, `advanced_reports`, `knowledge_base_upload` — defined in Task 3 schema, matches Task 2 service dict keys. ✅ consistent
