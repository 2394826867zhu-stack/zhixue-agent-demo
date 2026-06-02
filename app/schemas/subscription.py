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
    is_trial: bool = False           # E-04 · 当前 Pro 是否来自免费试用
    trial_available: bool = False    # E-04 · 是否还能领取免费试用
    features: SubscriptionFeatures

    model_config = {"from_attributes": True}
