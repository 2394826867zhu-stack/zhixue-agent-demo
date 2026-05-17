from pydantic import BaseModel


class OverviewOut(BaseModel):
    total_kps: int
    kp_delta_week: int
    mastery_distribution: dict[str, int]  # new/learning/reviewing/mastered
    today_tasks_total: int
    today_tasks_done: int
    weekly_pomodoros: int
    weekly_minutes: int
    due_cards: int
    mistake_count: int


class HeatmapDay(BaseModel):
    date: str   # YYYY-MM-DD
    minutes: int


class SubjectProgress(BaseModel):
    subject: str
    kp_count: int
    mastered_count: int
    mastery: float          # 0-100
    weekly_minutes: int
    flashcard_count: int
    wrong_count: int


class WeeklyReport(BaseModel):
    week_start: str
    week_end: str
    new_kps: int
    flashcard_completion_rate: float
    training_avg_score: float | None
    wrong_count: int
    pomodoro_count: int
    total_minutes: int
    weak_subjects: list[str]
    ai_advice: str
