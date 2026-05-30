"""用户 UI 偏好 API — v2 PRD 9.11 行 702"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user_prefs import UserPrefsOut, UserPrefsUpdate

router = APIRouter(prefix="/profile/prefs", tags=["UI 偏好"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.get("", summary="读取当前 UI 偏好（暗色 / 字号 / 动效 / haptic / 语音）")
async def get_prefs(
    user: User = Depends(get_current_user),
):
    out = UserPrefsOut(
        theme_mode=user.theme_mode,
        dynamic_type_scale=user.dynamic_type_scale,
        reduced_motion=user.reduced_motion,
        haptics_enabled=user.haptics_enabled,
        voice_enabled=user.voice_enabled,
    )
    return ok(out.model_dump())


@router.patch("", summary="更新 UI 偏好（任一字段可选）")
async def update_prefs(
    body: UserPrefsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = body.model_dump(exclude_none=True)
    for field, value in updated.items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    out = UserPrefsOut(
        theme_mode=user.theme_mode,
        dynamic_type_scale=user.dynamic_type_scale,
        reduced_motion=user.reduced_motion,
        haptics_enabled=user.haptics_enabled,
        voice_enabled=user.voice_enabled,
    )
    return ok(out.model_dump())
