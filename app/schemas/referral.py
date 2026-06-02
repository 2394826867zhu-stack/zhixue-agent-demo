"""E-10 · 邀请好友 Schema。"""
from pydantic import BaseModel, Field


class ReferralInfo(BaseModel):
    code: str
    referred_count: int
    reward_per_referral: int
    has_redeemed: bool


class RedeemRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=12)


class RedeemResult(BaseModel):
    reward_earned: int
    referrer_reward: int
