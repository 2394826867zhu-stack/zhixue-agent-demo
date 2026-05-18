import uuid
import logging
from datetime import datetime, timezone, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, and_, update
from passlib.context import CryptContext

from app.models.admin_user import AdminUser
from app.models.user import User
from app.models.token_usage import TokenUsage
from app.models.user_quota import UserQuota, DEFAULT_DAILY_TOKEN_LIMIT
from app.schemas.admin import AdminLoginRequest, UpdateUserRequest
from app.core.admin_auth import create_admin_token

logger = logging.getLogger(__name__)
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminService:

    # ---- Auth ----

    async def setup_first_admin(self, db: AsyncSession, email: str, password: str) -> AdminUser:
        count = (await db.execute(select(func.count()).select_from(AdminUser))).scalar()
        if count and count > 0:
            from app.core.exceptions import ValidationError
            raise ValidationError("管理员账号已存在，请直接登录")
        admin = AdminUser(
            email=email,
            password_hash=_pwd.hash(password),
            role="super_admin",
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin

    async def login(self, db: AsyncSession, body: AdminLoginRequest) -> dict:
        result = await db.execute(select(AdminUser).where(AdminUser.email == body.email))
        admin = result.scalar_one_or_none()
        if not admin or not _pwd.verify(body.password, admin.password_hash):
            from app.core.exceptions import ValidationError
            raise ValidationError("邮箱或密码错误")
        if not admin.is_active:
            from app.core.exceptions import ValidationError
            raise ValidationError("账号已禁用")
        admin.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        token = create_admin_token(str(admin.id), admin.role)
        return {"access_token": token, "admin_id": str(admin.id), "role": admin.role}

    # ---- Dashboard ----

    async def get_dashboard(self, db: AsyncSession) -> dict:
        today = date.today()
        seven_days_ago = today - timedelta(days=7)

        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

        active_today = (await db.execute(
            select(func.count()).select_from(User)
            .where(func.date(User.last_active_at) == today)
        )).scalar() or 0

        active_7d = (await db.execute(
            select(func.count()).select_from(User)
            .where(User.last_active_at >= datetime.combine(seven_days_ago, datetime.min.time()).replace(tzinfo=timezone.utc))
        )).scalar() or 0

        total_notes = (await db.execute(
            select(func.count()).select_from(text("notes"))
        )).scalar() or 0

        tokens_today = (await db.execute(
            select(func.sum(TokenUsage.total_tokens))
            .where(func.date(TokenUsage.created_at) == today)
        )).scalar() or 0

        tokens_7d = (await db.execute(
            select(func.sum(TokenUsage.total_tokens))
            .where(TokenUsage.created_at >= datetime.combine(seven_days_ago, datetime.min.time()).replace(tzinfo=timezone.utc))
        )).scalar() or 0

        cost_today = (await db.execute(
            select(func.sum(TokenUsage.cost_usd))
            .where(func.date(TokenUsage.created_at) == today)
        )).scalar() or 0.0

        cost_7d = (await db.execute(
            select(func.sum(TokenUsage.cost_usd))
            .where(TokenUsage.created_at >= datetime.combine(seven_days_ago, datetime.min.time()).replace(tzinfo=timezone.utc))
        )).scalar() or 0.0

        # Top 5 users by token usage today
        top_rows = (await db.execute(
            select(TokenUsage.user_id, func.sum(TokenUsage.total_tokens).label("tokens"))
            .where(func.date(TokenUsage.created_at) == today)
            .where(TokenUsage.user_id.isnot(None))
            .group_by(TokenUsage.user_id)
            .order_by(text("tokens DESC"))
            .limit(5)
        )).fetchall()

        top_users = []
        for row in top_rows:
            u = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
            top_users.append({
                "user_id": str(row.user_id),
                "email": u.email if u else "unknown",
                "tokens": row.tokens,
            })

        return {
            "total_users": total_users,
            "active_users_today": active_today,
            "active_users_7d": active_7d,
            "total_notes": total_notes,
            "total_tokens_today": int(tokens_today),
            "total_tokens_7d": int(tokens_7d),
            "total_cost_today_usd": round(float(cost_today), 6),
            "total_cost_7d_usd": round(float(cost_7d), 6),
            "top_token_users": top_users,
        }

    # ---- Users ----

    async def list_users(self, db: AsyncSession, search: str | None, page: int, page_size: int) -> dict:
        today = date.today()
        query = select(User).order_by(User.created_at.desc())
        if search:
            query = query.where(
                User.email.ilike(f"%{search}%") | User.nickname.ilike(f"%{search}%")
            )
        total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
        users = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()

        items = []
        for u in users:
            quota = await self._get_quota(db, u.id)
            tokens_today = await self._user_tokens_on(db, u.id, today)
            tokens_30d = await self._user_tokens_since(db, u.id, today - timedelta(days=30))
            notes_count = (await db.execute(
                select(func.count()).select_from(text("notes")).where(text(f"user_id = '{u.id}'"))
            )).scalar() or 0
            items.append({
                "id": str(u.id),
                "email": u.email,
                "nickname": u.nickname,
                "grade": u.grade,
                "plan_type": u.plan_type,
                "is_active": quota.is_active if quota else True,
                "created_at": u.created_at,
                "last_active_at": u.last_active_at,
                "total_notes": notes_count,
                "total_tokens_today": tokens_today,
                "total_tokens_30d": tokens_30d,
                "daily_token_limit": quota.daily_token_limit if quota else DEFAULT_DAILY_TOKEN_LIMIT,
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_user_detail(self, db: AsyncSession, user_id: str) -> dict:
        u = (await db.execute(select(User).where(User.id == uuid.UUID(user_id)))).scalar_one_or_none()
        if not u:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("用户")

        today = date.today()
        quota = await self._get_quota(db, u.id)

        # 7天每日 token 用量
        token_7d = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            tokens = await self._user_tokens_on(db, u.id, d)
            cost = (await db.execute(
                select(func.sum(TokenUsage.cost_usd))
                .where(TokenUsage.user_id == u.id)
                .where(func.date(TokenUsage.created_at) == d)
            )).scalar() or 0.0
            token_7d.append({"date": d.isoformat(), "total_tokens": tokens, "cost_usd": round(float(cost), 6)})

        from app.models.training import TrainingSession
        from app.models.flashcard import Flashcard
        training_count = (await db.execute(
            select(func.count()).select_from(TrainingSession).where(TrainingSession.user_id == u.id)
        )).scalar() or 0
        notes_count = (await db.execute(
            select(func.count()).select_from(text("notes")).where(text(f"user_id = '{u.id}'"))
        )).scalar() or 0

        return {
            "id": str(u.id),
            "email": u.email,
            "nickname": u.nickname,
            "grade": u.grade,
            "plan_type": u.plan_type,
            "is_active": quota.is_active if quota else True,
            "created_at": u.created_at,
            "last_active_at": u.last_active_at,
            "total_notes": notes_count,
            "total_tokens_today": await self._user_tokens_on(db, u.id, today),
            "total_tokens_30d": await self._user_tokens_since(db, u.id, today - timedelta(days=30)),
            "daily_token_limit": quota.daily_token_limit if quota else DEFAULT_DAILY_TOKEN_LIMIT,
            "onboarding_completed": u.onboarding_completed,
            "learning_profile": u.learning_profile,
            "total_flashcard_reviews": 0,  # could join fsrs_states
            "total_training_sessions": training_count,
            "token_usage_7d": token_7d,
        }

    async def update_user(self, db: AsyncSession, user_id: str, body: UpdateUserRequest) -> dict:
        uid = uuid.UUID(user_id)
        u = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if not u:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("用户")

        if body.plan_type is not None:
            u.plan_type = body.plan_type

        quota = await self._get_quota(db, uid)
        if quota is None:
            quota = UserQuota(user_id=uid)
            db.add(quota)
        if body.daily_token_limit is not None:
            quota.daily_token_limit = body.daily_token_limit
        if body.is_active is not None:
            quota.is_active = body.is_active
        if body.notes is not None:
            quota.notes = body.notes

        await db.commit()
        return {"success": True}

    # ---- Token Usage ----

    async def get_token_stats(self, db: AsyncSession, days: int = 7) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        total_calls = (await db.execute(
            select(func.count()).select_from(TokenUsage).where(TokenUsage.created_at >= since)
        )).scalar() or 0

        total_tokens = (await db.execute(
            select(func.sum(TokenUsage.total_tokens)).where(TokenUsage.created_at >= since)
        )).scalar() or 0

        total_cost = (await db.execute(
            select(func.sum(TokenUsage.cost_usd)).where(TokenUsage.created_at >= since)
        )).scalar() or 0.0

        by_model_rows = (await db.execute(
            select(TokenUsage.model, func.sum(TokenUsage.total_tokens).label("t"), func.sum(TokenUsage.cost_usd).label("c"))
            .where(TokenUsage.created_at >= since)
            .group_by(TokenUsage.model)
            .order_by(text("t DESC"))
        )).fetchall()
        by_model = [{"model": r.model, "total_tokens": int(r.t or 0), "cost_usd": round(float(r.c or 0), 6)} for r in by_model_rows]

        by_day = []
        today = date.today()
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            t = await self._tokens_on(db, d)
            c = (await db.execute(
                select(func.sum(TokenUsage.cost_usd)).where(func.date(TokenUsage.created_at) == d)
            )).scalar() or 0.0
            by_day.append({"date": d.isoformat(), "total_tokens": t, "cost_usd": round(float(c), 6)})

        top_rows = (await db.execute(
            select(TokenUsage.user_id, func.sum(TokenUsage.total_tokens).label("t"))
            .where(TokenUsage.created_at >= since)
            .where(TokenUsage.user_id.isnot(None))
            .group_by(TokenUsage.user_id)
            .order_by(text("t DESC"))
            .limit(10)
        )).fetchall()
        top_users = []
        for row in top_rows:
            u = (await db.execute(select(User).where(User.id == row.user_id))).scalar_one_or_none()
            top_users.append({"user_id": str(row.user_id), "email": u.email if u else "?", "total_tokens": int(row.t or 0)})

        return {
            "total_calls": total_calls,
            "total_tokens": int(total_tokens),
            "total_cost_usd": round(float(total_cost), 6),
            "by_model": by_model,
            "by_day": by_day,
            "top_users": top_users,
        }

    async def get_user_token_history(self, db: AsyncSession, user_id: str, limit: int = 50) -> list:
        rows = (await db.execute(
            select(TokenUsage)
            .where(TokenUsage.user_id == uuid.UUID(user_id))
            .order_by(TokenUsage.created_at.desc())
            .limit(limit)
        )).scalars().all()
        return [
            {
                "id": str(r.id), "model": r.model, "endpoint": r.endpoint,
                "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens, "cost_usd": r.cost_usd,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def set_quota(self, db: AsyncSession, user_id: str, limit: int, notes: str | None) -> dict:
        uid = uuid.UUID(user_id)
        quota = await self._get_quota(db, uid)
        if quota is None:
            quota = UserQuota(user_id=uid, daily_token_limit=limit, notes=notes)
            db.add(quota)
        else:
            quota.daily_token_limit = limit
            if notes is not None:
                quota.notes = notes
            quota.updated_at = datetime.now(timezone.utc)
        await db.commit()
        # 同步更新 Redis
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            await r.set(f"quota:{user_id}:daily_limit", limit)
        except Exception:
            pass
        return {"user_id": user_id, "daily_token_limit": limit}

    # ---- Helpers ----

    async def _get_quota(self, db: AsyncSession, user_id: uuid.UUID) -> UserQuota | None:
        return (await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))).scalar_one_or_none()

    async def _user_tokens_on(self, db: AsyncSession, user_id: uuid.UUID, d: date) -> int:
        v = (await db.execute(
            select(func.sum(TokenUsage.total_tokens))
            .where(TokenUsage.user_id == user_id)
            .where(func.date(TokenUsage.created_at) == d)
        )).scalar()
        return int(v or 0)

    async def _user_tokens_since(self, db: AsyncSession, user_id: uuid.UUID, since: date) -> int:
        v = (await db.execute(
            select(func.sum(TokenUsage.total_tokens))
            .where(TokenUsage.user_id == user_id)
            .where(func.date(TokenUsage.created_at) >= since)
        )).scalar()
        return int(v or 0)

    async def _tokens_on(self, db: AsyncSession, d: date) -> int:
        v = (await db.execute(
            select(func.sum(TokenUsage.total_tokens))
            .where(func.date(TokenUsage.created_at) == d)
        )).scalar()
        return int(v or 0)


admin_service = AdminService()
