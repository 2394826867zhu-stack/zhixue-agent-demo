from typing import Any
from pydantic import BaseModel


STEPS = ["grade", "subjects", "progress", "performance", "next_exam", "goal", "upload", "confirm"]
TOTAL_STEPS = len(STEPS)


class OnboardingChatRequest(BaseModel):
    message: str


class OnboardingChatResponse(BaseModel):
    reply: str
    step: str              # current step name after this turn
    step_index: int        # 0-based index (TOTAL_STEPS = completed)
    total_steps: int
    completed: bool
    profile_draft: dict[str, Any]


class OnboardingStatusOut(BaseModel):
    current_step: str
    step_index: int
    total_steps: int
    completed: bool
    question: str          # the prompt text for current step
    profile_draft: dict[str, Any]
