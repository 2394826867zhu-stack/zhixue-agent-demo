"""用户 UI 偏好 API — v2 PRD 9.11 + C-21 通知偏好"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user_prefs import UserPrefsOut, UserPrefsUpdate
from app.schemas.envelope import Envelope

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


@router.get("", summary="读取当前 UI 偏好与通知设置", response_model=Envelope[UserPrefsOut])
async def get_prefs(
    user: User = Depends(get_current_user),
):
    return ok(_to_out(user).model_dump())


@router.patch("", summary="更新 UI 偏好与通知设置（任一字段可选）", response_model=Envelope[UserPrefsOut])
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
