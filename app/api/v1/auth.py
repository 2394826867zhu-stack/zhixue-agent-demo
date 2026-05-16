from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshRequest,
    TokenResponse, UserProfile, UpdateProfileRequest,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


def ok(data):
    return {"code": 200, "message": "success", "data": data}


@router.post("/register", summary="注册")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register(db, body)
    tokens = await auth_service.login(db, LoginRequest(email=body.email, password=body.password))
    return ok(TokenResponse(**tokens))


@router.post("/login", summary="登录")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login(db, body)
    return ok(TokenResponse(**tokens))


@router.post("/refresh", summary="刷新 Token")
async def refresh(body: RefreshRequest):
    tokens = await auth_service.refresh_token(body.refresh_token)
    return ok(TokenResponse(**tokens))


@router.post("/logout", summary="登出")
async def logout(body: RefreshRequest, _: User = Depends(get_current_user)):
    await auth_service.logout(body.refresh_token)
    return ok(None)


@router.get("/me", summary="获取当前用户信息")
async def get_me(user: User = Depends(get_current_user)):
    return ok(UserProfile.model_validate(user))


@router.patch("/me", summary="更新用户资料")
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await auth_service.update_profile(db, user, body)
    return ok(UserProfile.model_validate(updated))
