from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Any


# ---- Auth ----
class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin_id: str
    role: str


class AdminSetupRequest(BaseModel):
    email: EmailStr
    password: str
    secret_key: str  # 首次创建时需要和 ADMIN_JWT_SECRET 匹配


# ---- Dashboard ----
class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    active_users_7d: int
    total_notes: int
    total_tokens_today: int
    total_tokens_7d: int
    total_cost_today_usd: float
    total_cost_7d_usd: float
    top_token_users: list[dict]


# ---- Users ----
class AdminUserItem(BaseModel):
    id: str
    email: str
    nickname: str | None
    grade: str | None
    plan_type: str
    is_active: bool
    created_at: datetime
    last_active_at: datetime | None
    total_notes: int
    total_tokens_today: int
    total_tokens_30d: int
    daily_token_limit: int


class AdminUserDetail(AdminUserItem):
    onboarding_completed: bool
    learning_profile: dict | None
    total_flashcard_reviews: int
    total_training_sessions: int
    token_usage_7d: list[dict]  # [{date, total_tokens, cost_usd}]


class UserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int
    page: int
    page_size: int


class UpdateUserRequest(BaseModel):
    daily_token_limit: int | None = None
    is_active: bool | None = None
    notes: str | None = None
    plan_type: str | None = None


# ---- Token Usage ----
class TokenUsageItem(BaseModel):
    id: str
    user_id: str | None
    model: str
    endpoint: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    created_at: datetime


class TokenStatsResponse(BaseModel):
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    by_model: list[dict]
    by_day: list[dict]
    top_users: list[dict]


class QuotaUpdateRequest(BaseModel):
    daily_token_limit: int
    notes: str | None = None
