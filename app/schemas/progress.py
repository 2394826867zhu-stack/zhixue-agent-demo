from pydantic import BaseModel


class OverviewOut(BaseModel):
    total_kp: int
    mastery_distribution: dict[str, int]  # new/learning/reviewing/mastered
    today_tasks_total: int
    today_tasks_done: int
    week_pomodoro_count: int
    week_study_minutes: int
    total_wrong: int
    total_flashcards: int


class HeatmapDay(BaseModel):
    date: str   # YYYY-MM-DD
    minutes: int


class SubjectProgress(BaseModel):
    subject: str
    kp_count: int
    mastered_count: int
    mastery_rate: float
    flashcard_count: int
    wrong_count: int


class WeeklyReport(BaseModel):
    week_start: str
    week_end: str
    new_kp_count: int
    flashcard_completion_rate: float
    avg_training_score: float | None
    wrong_count: int
    pomodoro_count: int
    study_minutes: int
    weak_subjects: list[str]
    ai_advice: str
