import uuid
from datetime import datetime, timezone
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.schemas.auth import (
    RegisterRequest, LoginRequest, UpdateProfileRequest, ChangePasswordRequest,
)
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.redis import get_redis
from app.core.exceptions import (
    AppError, TokenExpiredError, NotFoundError, ValidationError
)
from app.config import settings

REFRESH_BLACKLIST_PREFIX = "refresh_blacklist:"


class AuthService:

    async def register(self, db: AsyncSession, data: RegisterRequest) -> User:
        # 检查邮箱是否已注册
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ValidationError("该邮箱已被注册")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            nickname=data.nickname,
            grade=data.grade,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def login(self, db: AsyncSession, data: LoginRequest) -> dict:
        result = await db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise AppError(4003, "邮箱或密码错误", 401)

        # 更新最后活跃时间
        user.last_active_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "access_token": create_access_token(str(user.id)),
            "refresh_token": create_refresh_token(str(user.id)),
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        # 检查黑名单
        redis = await get_redis()
        if await redis.get(f"{REFRESH_BLACKLIST_PREFIX}{refresh_token}"):
            raise TokenExpiredError()

        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise TokenExpiredError()

        if payload.get("type") != "refresh":
            raise TokenExpiredError()

        user_id = payload.get("sub")
        # P1-11 · refresh token 轮换：旧 token 用后即拉黑，杜绝被盗 refresh token 无限重放
        # （刷出新 token 后旧的立即失效，再次使用命中黑名单被拒）。
        await self.logout(refresh_token)
        return {
            "access_token": create_access_token(user_id),
            "refresh_token": create_refresh_token(user_id),
        }

    async def logout(self, refresh_token: str):
        redis = await get_redis()
        expire_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        await redis.set(
            f"{REFRESH_BLACKLIST_PREFIX}{refresh_token}",
            "1",
            ex=expire_seconds,
        )

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> User:
        result = await db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("用户")
        return user

    async def change_password(
        self, db: AsyncSession, user: User, data: ChangePasswordRequest
    ) -> None:
        # 校验旧密码（不匹配 → 401，明确区别于校验失败）
        if not verify_password(data.old_password, user.password_hash):
            raise AppError(4003, "原密码不正确", 401)
        # 新密码强度已由 schema 校验（复用注册规则，<8 位 422）
        user.password_hash = hash_password(data.new_password)
        await db.commit()

    async def update_profile(
        self, db: AsyncSession, user: User, data: UpdateProfileRequest
    ) -> User:
        if data.nickname is not None:
            user.nickname = data.nickname
        if data.grade is not None:
            user.grade = data.grade
        if data.subjects is not None:
            user.subjects = data.subjects
        await db.commit()
        await db.refresh(user)
        return user


auth_service = AuthService()
