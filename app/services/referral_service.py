"""E-10 · 邀请好友业务逻辑。

- referral_code：每用户唯一短码，首次访问邀请页时懒生成。
- redeem：新用户填写邀请码 → 记 referred_by + 双方各得知星奖励。
- 守卫：不能填自己的码、不能重复填、码必须存在。
"""
import secrets
import uuid

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.models.user import User
from app.models.star import StarLedger

# 邀请奖励：邀请人与被邀请人各得
REFERRAL_REWARD = 50
CODE_LEN = 8
# 去除易混字符（0/O/1/I/L）
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LEN))


async def get_or_create_code(db: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    # 生成唯一码（碰撞重试）
    for _ in range(10):
        code = _gen_code()
        exists = (
            await db.execute(select(User.id).where(User.referral_code == code))
        ).scalar_one_or_none()
        if exists is None:
            user.referral_code = code
            await db.commit()
            await db.refresh(user)
            return code
    raise AppError(5000, "邀请码生成失败，请重试", 500)


async def get_info(db: AsyncSession, user: User) -> dict:
    code = await get_or_create_code(db, user)
    referred_count = (
        await db.execute(
            select(func.count()).select_from(User).where(User.referred_by == user.id)
        )
    ).scalar_one()
    return {
        "code": code,
        "referred_count": int(referred_count),
        "reward_per_referral": REFERRAL_REWARD,
        "has_redeemed": user.referred_by is not None,
    }


async def redeem(db: AsyncSession, user: User, code: str) -> dict:
    code = code.strip().upper()
    if user.referred_by is not None:
        raise AppError(4003, "你已经填过邀请码啦", 400)
    if user.referral_code and code == user.referral_code:
        raise AppError(4003, "不能填自己的邀请码哦", 400)

    referrer = (
        await db.execute(select(User).where(User.referral_code == code))
    ).scalar_one_or_none()
    if referrer is None:
        raise NotFoundError("邀请码")
    if referrer.id == user.id:
        raise AppError(4003, "不能填自己的邀请码哦", 400)

    # P0-2 · 原子 CAS：仅当 referred_by 仍为空才占位，杜绝并发重复填码 + 双发知星。
    # 先查后写(check-then-act)无锁时，两个并发请求都能穿透上面的 None 判断各发一次 50 星；
    # 这里把"占位"压成单条带 WHERE 的 UPDATE，靠 rowcount 区分赢家。
    cas = await db.execute(
        update(User)
        .where(User.id == user.id, User.referred_by.is_(None))
        .values(referred_by=referrer.id)
    )
    if cas.rowcount != 1:
        # 竞态下另一请求已抢先填码（或本就已填）→ 不重复发星
        await db.rollback()
        raise AppError(4003, "你已经填过邀请码啦", 400)

    # 双方各得知星（仅 CAS 赢家走到这里）
    db.add(StarLedger(
        user_id=referrer.id, amount=REFERRAL_REWARD, reason="invite_friend",
        description="好友接受了你的邀请", meta={"referee_id": str(user.id)},
    ))
    db.add(StarLedger(
        user_id=user.id, amount=REFERRAL_REWARD, reason="invite_friend",
        description="使用邀请码奖励", meta={"referrer_id": str(referrer.id)},
    ))
    await db.commit()
    # 同步内存对象，保持后续 get_info / 响应一致（core update 不回写 identity map）
    user.referred_by = referrer.id
    return {"reward_earned": REFERRAL_REWARD, "referrer_reward": REFERRAL_REWARD}
