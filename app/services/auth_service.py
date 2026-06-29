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

    async def delete_account(self, db: AsyncSession, user: User) -> None:
        """注销账号：永久删除用户及其全部数据（隐私政策"注销后永久删除"）。

        P1-11：多数表靠 FK ondelete=CASCADE 随 users 行删除，但以下 4 张审计/用量表
        的 user_id 是**裸列无 FK**，不会被级联清理——必须显式 DELETE，否则注销后残留
        孤儿数据（含 agent_tool_traces.arguments / rag_retrieval_traces.masked_query
        等用户行为/内容残留）。
        P2-5：用户上传的物理文件也不随 DB 行删除，best-effort 清盘。
        """
        from sqlalchemy import delete as _delete, select as _select
        from app.models.agent_tool_trace import AgentToolTrace
        from app.models.rag_retrieval_trace import RagRetrievalTrace
        from app.models.token_usage import TokenUsage
        from app.models.user_quota import UserQuota
        from app.models.file_upload import FileUpload

        uid = user.id

        # P2-5：先按归属取出磁盘文件名，删 DB 行前 best-effort 删盘（删行后查不到归属）。
        try:
            import os
            stored = (await db.execute(
                _select(FileUpload.stored_filename).where(FileUpload.user_id == uid)
            )).scalars().all()
            for fname in stored:
                path = os.path.join(settings.LOCAL_UPLOAD_DIR, os.path.basename(fname))
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass  # 单个文件删失败不阻断注销
        except Exception:  # noqa: BLE001 — 磁盘清理是 best-effort，不阻断账号删除
            pass

        # P1-11：显式清无 FK 的审计/用量表（顺序无所谓，都是裸 user_id 列）。
        for model in (AgentToolTrace, RagRetrievalTrace, TokenUsage, UserQuota):
            await db.execute(_delete(model).where(model.user_id == uid))

        # 其余有 FK 的表随 users 行 ondelete=CASCADE 级联删除。
        await db.delete(user)
        await db.commit()


auth_service = AuthService()
