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
