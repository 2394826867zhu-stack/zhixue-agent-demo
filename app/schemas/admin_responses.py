"""admin 端点响应 schema（SDD Phase 0 精度收口）。

内部管理/统计端点。顶层字段精确类型；嵌套子聚合（by_model / by_day /
top_users / token_7d / samples / thread items）用 list[dict]/dict —— 它们是
动态子表，admin 面板按需读，不强行展开成深层 schema（也避免误删字段）。
"""
from datetime import datetime
from pydantic import BaseModel


class AdminSetupResult(BaseModel):
    admin_id: str
    email: str
    role: str


class DashboardOut(BaseModel):
    total_users: int
    active_users_today: int
    active_users_7d: int
    total_notes: int
    total_tokens_today: int
    total_tokens_7d: int
    total_cost_today_usd: float
    total_cost_7d_usd: float
    top_token_users: list[dict]
    total_projects: int
    active_projects: int
    total_immersion_sessions: int
    total_focus_minutes: int
    total_ss_timeline_nodes: int


class AdminUserListItem(BaseModel):
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


class AdminUserListResponse(BaseModel):
    items: list[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminUserDetail(AdminUserListItem):
    onboarding_completed: bool
    learning_profile: dict | None
    total_flashcard_reviews: int
    total_training_sessions: int
    token_usage_7d: list[dict]


class AdminUpdateResult(BaseModel):
    success: bool


class TokenStatsOut(BaseModel):
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    by_model: list[dict]
    by_day: list[dict]
    top_users: list[dict]


class TokenHistoryItem(BaseModel):
    id: str
    model: str | None
    endpoint: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    created_at: datetime


class AdminQuotaOut(BaseModel):
    user_id: str
    daily_token_limit: int
    notes: str | None = None
    is_default: bool
    updated_at: str | None = None


class AdminSetQuotaResult(BaseModel):
    user_id: str
    daily_token_limit: int


class AdminConfigOut(BaseModel):
    feature_flags: dict
    min_app_version: str | None = None
    announcement: dict | None = None
    updated_at: str | None = None


class DeadLetterItem(BaseModel):
    id: str
    task_name: str
    task_id: str | None
    error: str | None
    retries: int
    resolved: bool
    created_at: str | None


class DeadLetterResolveResult(BaseModel):
    id: str
    resolved: bool


class RagBackfillResult(BaseModel):
    queued: bool
    user_id: str


class RecallStatsOut(BaseModel):
    window_days: int
    total: int
    empty_count: int
    empty_rate: float
    avg_score: float | None
    low_score_threshold: float
    low_score_count: int
    kind_totals: dict


class LowQualitySamplesOut(BaseModel):
    count: int
    samples: list[dict]


class AdminThreadListResponse(BaseModel):
    items: list[dict]   # thread 摘要子表（id/user_id/subject/status/时间...）
    total: int
    page: int
    page_size: int


class FaqItemAdminOut(BaseModel):
    id: str
    category: str
    question: str
    answer: str
    sort_order: int
    is_published: bool
    updated_at: str | None = None
