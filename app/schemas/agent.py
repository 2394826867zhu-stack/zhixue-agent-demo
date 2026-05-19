from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    studyspace_session_id: str | None = None
    image_url: str | None = None
