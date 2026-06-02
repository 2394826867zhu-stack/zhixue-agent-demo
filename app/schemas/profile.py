import uuid
from datetime import datetime, date, timedelta
from pydantic import BaseModel, field_validator, computed_field


class InsightsOut(BaseModel):
    # 笔记
    total_notes: int
    # 知识点
    total_kps: int
    mastered_kps: int
    # 专注
    total_focus_minutes: int
    total_pomodoros: int
    # 复习
    total_flashcard_reviews: int
    # 训练
    total_training_sessions: int
    training_avg_score: float | None
    # 引导问答
    total_guidance_sessions: int
    # 连续学习天数（基于番茄钟/任务记录）
    streak_days: int
    # 成就
    achievements_earned: int
    achievements_total: int


class AchievementOut(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    earned: bool
    progress: int        # 当前值
    target: int          # 达成目标值
    progress_pct: int    # 0-100


class ReflectionCreate(BaseModel):
    content: str
    week_start: date | None = None  # 不传则默认本周一

    @field_validator("content")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("复盘内容不能为空")
        if len(v) > 5000:
            raise ValueError("复盘内容不能超过5000字")
        return v


class ReflectionOut(BaseModel):
    id: uuid.UUID
    week_start: date
    content: str
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=6)

    model_config = {"from_attributes": True}


class TokenQuotaOut(BaseModel):
    """F-10 · 今日 token 配额余量（profile_service.get_token_quota）。"""
    date: str
    used: int
    daily_limit: int
    remaining: int
    is_default_limit: bool


class ProfileUpdateResult(BaseModel):
    nickname: str | None = None
    grade: str | None = None
    subjects: list[str] = []


class VoiceToggleResult(BaseModel):
    voice_enabled: bool


class ReflectionGenerateResult(BaseModel):
    """主动触发本周复盘生成的返回（weekly_reflection_tasks._generate_for_user）。"""
    user_id: str
    week_start: str
    len: int
