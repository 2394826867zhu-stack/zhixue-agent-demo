from pydantic import BaseModel


class MasteryDistribution(BaseModel):
    struggling: int   # p_mastery < 0.3
    learning: int     # 0.3 <= p_mastery <= 0.7
    mastered: int     # p_mastery > 0.7
    unprobed: int     # p_mastery is None


class WeeklyReportOut(BaseModel):
    week_start: str
    week_end: str
    new_kps: int
    flashcard_completion_rate: float
    training_avg_score: float | None
    wrong_count: int
    pomodoro_count: int
    total_minutes: int
    checkin_count: int
    mastery_distribution: MasteryDistribution
    avg_p_mastery: float | None
    weak_subjects: list[str]
    weak_kp_names: list[str]
    ai_advice: str
