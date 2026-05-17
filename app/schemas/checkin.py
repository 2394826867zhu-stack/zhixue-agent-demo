from datetime import datetime
from typing import Any
from pydantic import BaseModel


class CheckInRequest(BaseModel):
    content: str


class CheckInOut(BaseModel):
    id: str
    raw_content: str
    ai_summary: str | None
    parsed_updates: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        # coerce UUID to str
        if hasattr(self, "__dict__") and not isinstance(self.id, str):
            object.__setattr__(self, "id", str(self.id))
