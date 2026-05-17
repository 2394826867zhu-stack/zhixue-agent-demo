from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
